# This file is part of OpenHatch.
# Copyright (C) 2010, 2011 Jack Grigg
# Copyright (C) 2010 OpenHatch, Inc.
# Copyright (C) 2012 Berry Phillips.
# Copyright (C) 2012 Asheesh Laroia.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import lxml
import urlparse
import logging
import scrapy

import bugimporters.items
from bugimporters.base import BugImporter
from bugimporters.helpers import cached_property, string2naive_datetime

### The design of the BugzillaBugImporter has always been very special.
#
### We get bug data by executing a show_bug.cgi?ctype=xml query against the
### bug tracker in question.
#
### We populate that query with a list of bug IDs that we care about. In
### general, we want to issue fairly few show_bug?ctype=xml queries, just
### to be nice to the remote bug tracker.
#
### This list of bug IDs comes from a few places.
#
### First, and very easily, it comes from the list of bugs we are told
### we already have crawled.
#
### Second, and more complicated: we execute a number of queries against
### the remote bug tracker to get a list of bug IDs we *should* care about.
### This includes queries about bitesize bugs in the remote bug tracker.
### The current implementation takes the approach that, after we finish
### extracting the list of bug IDs we care about, it calls a method to
### enqueue a request (if required) to make sure those bug IDs are fetched.
###
### To avoid duplicates, that method stores some state in the
### BugzillaBugImporter instance to indicate it has queued up a request for
### data on those bugs. That way, if the method is called repeatedly with
### bug IDs which we are in the middle of downloading, we carefully refuse to
### re-download them and waste time on the poor remote bug tracker.

class BugzillaBugImporter(BugImporter):
    def __init__(self, *args, **kwargs):
        # Call the parent __init__.
        super(BugzillaBugImporter, self).__init__(*args, **kwargs)

        if self.bug_parser is None:
            self.bug_parser = BugzillaBugParser

        # Create a set of bug IDs whose data we have already enqueued
        # a request for.
        self.already_enqueued_bug_ids = set()

    def process_queries(self, queries):
        for query_url in queries:
            # Add the query URL and generic callback.
            # Note that we don't know what exact type of query this is:
            # a tracking bug, or just something that returns Bugzilla XML.
            # We get to disambiguate in the callback.
            yield scrapy.http.Request(url=query_url,
                    callback=self.handle_query_response)

    def handle_query_response(self, response):
        # Find out what type of query this is.

        # Is it XML?
        first_100_bytes =  response.body[:100]
        if first_100_bytes.strip().startswith("<?xml"):
            bug_ids = self.handle_tracking_bug_xml(response.body)

        # Else, assume it's some kind of HTML.
        bug_ids = self.handle_query_html(response.body)

        # Either way, enqueue the work of downloading information about those
        # bugs.
        for request in self.generate_requests_for_bugs(bug_ids):
            yield request

    def handle_query_html(self, query_html_string):
        # Turn the string into an HTML tree that can be parsed to find the list
        # of bugs hidden in the 'XML' form.
        query_html = lxml.etree.HTML(query_html_string)
        # Find all form inputs at the level we want.
        # This amounts to around three forms.
        query_form_inputs = query_html.xpath('/html/body/div/table/tr/td/form/input')
        # Extract from this the inputs corresponding to 'ctype' fields.
        ctype_inputs = [i for i in query_form_inputs if 'ctype' in i.values()]
        # Limit this to inputs with 'ctype=xml'.
        ctype_xml = [i for i in ctype_inputs if 'xml' in i.values()]
        if ctype_xml:
            # Get the 'XML' form.
            xml_form = ctype_xml[0].getparent()
            # Get all its children.
            xml_inputs = xml_form.getchildren()
            # Extract from this all bug id inputs.
            bug_id_inputs = [i for i in xml_inputs if 'id' in i.values()]
            # Convert this to a list of bug ids.
            bug_id_list = [int(i.get('value')) for i in bug_id_inputs]
            # Add them to self.bug_ids.
            return bug_id_list

    def handle_tracking_bug_xml(self, tracking_bug_xml_string):
        # Turn the string into an XML tree.
        tracking_bug_xml = lxml.etree.XML(tracking_bug_xml_string)
        # Find all the bugs that this tracking bug depends on.
        depends = tracking_bug_xml.findall('bug/dependson')
        # Add them to self.bug_ids.
        self.bug_ids.extend([int(depend.text) for depend in depends])

    def process_bugs(self, bug_list):
        bug_urls = [bug_url for (bug_url, _) in bug_list]
        bug_ids = []
        for bug_url in bug_urls:
            _, after = bug_url.split('?', 1)
            as_dict = urlparse.parse_qs(after)
            bug_ids.extend(as_dict['id'])

        for request in self.generate_requests_for_bugs(map(int, bug_ids)):
            yield request

    def generate_requests_for_bugs(self, bug_ids, AT_A_TIME=50):
        '''Note that this method is not implemented in a thread-safe
        way. It exploits the fact that we are only doing asynchronous
        I/O, not threaded processing.'''
        bug_ids_to_request = sorted(set([
                    bug_id
                    for bug_id in bug_ids
                    if bug_id not in self.already_enqueued_bug_ids]))

        first_n, rest = (bug_ids_to_request[:AT_A_TIME],
                         bug_ids_to_request[AT_A_TIME:])
        while first_n:
            # Create a single URL to fetch all the bug data.
            big_url = urlparse.urljoin(
                self.tm.get_base_url(),
                'show_bug.cgi?ctype=xml&excludefield=attachmentdata')
            big_url += '&'
            for bug_id in first_n:
                big_url += "id=%d&" % (bug_id,)

            # Create the corresponding request object
            r = scrapy.http.Request(url=big_url,
                                    callback=self.handle_bug_xml_response)

            # Update the 'rest' of the work
            first_n, rest = (rest[:AT_A_TIME],
                             rest[AT_A_TIME:])

            # Signal that we have these bug IDs taken care of.
            self.already_enqueued_bug_ids.update(set(first_n))

            # yield the Request so it actually gets handled
            yield r

    def handle_bug_xml_response(self, response):
        return self.handle_bug_xml(response.body)

    def handle_bug_xml(self, bug_list_xml_string):
        logging.info("STARTING XML")
        # Turn the string into an XML tree.
        try:
            bug_list_xml = lxml.etree.XML(bug_list_xml_string)
        except Exception:
            logging.exception("Eek, XML parsing failed. Jumping to the errback.")
            logging.error("If this keeps happening, you might want to "
                          "delete/disable the bug tracker causing this.")
            raise

        return self.handle_bug_list_xml_parsed(bug_list_xml)

    def handle_bug_list_xml_parsed(self, bug_list_xml):
        for bug_xml in bug_list_xml.xpath('bug'):
            # Create a BugzillaBugParser with the XML data.
            bbp = self.bug_parser(bug_xml)

            # Get the parsed data dict from the BugzillaBugParser.
            data = bbp.get_parsed_data_dict(base_url=self.tm.get_base_url(),
                                            bitesized_type=self.tm.bitesized_type,
                                            bitesized_text=self.tm.bitesized_text,
                                            documentation_type=self.tm.documentation_type,
                                            documentation_text=self.tm.documentation_text)

            data.update({
                'canonical_bug_link': bbp.bug_url,
                '_tracker_name': self.tm.tracker_name,
                '_project_name': bbp.generate_bug_project_name(
                        bug_project_name_format=self.tm.bug_project_name_format,
                        tracker_name=self.tm.tracker_name),
            })

            yield data

class BugzillaBugParser:
    @staticmethod
    def get_tag_text_from_xml(xml_doc, tag_name, index = 0):
        """Given an object representing <bug><tag>text</tag></bug>,
        and tag_name = 'tag', returns 'text'.

        If someone carelessly passes us something else, we bail
        with ValueError."""
        if xml_doc.tag != 'bug':
            error_msg = "You passed us a %s tag. We wanted a <bug> object." % (
                xml_doc.tag,)
            raise ValueError, error_msg
        tags = xml_doc.xpath(tag_name)
        try:
            return tags[index].text or u''
        except IndexError:
            return ''

    def __init__(self, bug_xml):
        self.bug_xml = bug_xml
        self.bug_id = self._bug_id_from_bug_data()
        self.bug_url = None # This gets filled in the data parser.

    def _bug_id_from_bug_data(self):
        return int(self.get_tag_text_from_xml(self.bug_xml, 'bug_id'))

    @cached_property
    def product(self):
        return self.get_tag_text_from_xml(self.bug_xml, 'product')

    @cached_property
    def component(self):
        return self.get_tag_text_from_xml(self.bug_xml, 'component')

    @staticmethod
    def _who_tag_to_username_and_realname(who_tag):
        username = who_tag.text
        realname = who_tag.attrib.get('name', '')
        return username, realname

    @staticmethod
    def bugzilla_count_people_involved(xml_doc):
        """Strategy: Create a set of all the listed text values
        inside a <who ...>(text)</who> tag
        Return the length of said set."""
        everyone = [tag.text for tag in xml_doc.xpath('.//who')]
        return len(set(everyone))

    @staticmethod
    def bugzilla_date_to_printable_datetime(date_string):
        return string2naive_datetime(date_string).isoformat()

    def get_parsed_data_dict(self,
                             base_url, bitesized_type, bitesized_text,
                             documentation_type, documentation_text):
        # Generate the bug_url.
        self.bug_url = urlparse.urljoin(
                base_url,
                'show_bug.cgi?id=%d' % self.bug_id)

        xml_data = self.bug_xml

        date_reported_text = self.get_tag_text_from_xml(xml_data, 'creation_ts')
        last_touched_text = self.get_tag_text_from_xml(xml_data, 'delta_ts')
        u, r = self._who_tag_to_username_and_realname(xml_data.xpath('.//reporter')[0])
        status = self.get_tag_text_from_xml(xml_data, 'bug_status')
        looks_closed = status in ('RESOLVED', 'WONTFIX', 'CLOSED', 'ASSIGNED')

        ret_dict = bugimporters.items.ParsedBug({
            'title': self.get_tag_text_from_xml(xml_data, 'short_desc'),
            'description': (self.get_tag_text_from_xml(xml_data, 'long_desc/thetext') or
                           '(Empty description)'),
            'status': status,
            'importance': self.get_tag_text_from_xml(xml_data, 'bug_severity'),
            'people_involved': self.bugzilla_count_people_involved(xml_data),
            'date_reported': self.bugzilla_date_to_printable_datetime(
                    date_reported_text),
            'last_touched': self.bugzilla_date_to_printable_datetime(
                    last_touched_text),
            'submitter_username': u,
            'submitter_realname': r,
            'canonical_bug_link': self.bug_url,
            'looks_closed': looks_closed
            })
        keywords_text = self.get_tag_text_from_xml(xml_data, 'keywords') or ''
        keywords = map(lambda s: s.strip(),
                       keywords_text.split(','))
        # Check for the bitesized keyword
        if bitesized_type:
            b_list = bitesized_text.split(',')
            if bitesized_type == 'key':
                ret_dict['good_for_newcomers'] = any(b in keywords for b in b_list)
            elif bitesized_type == 'wboard':
                whiteboard_text = self.get_tag_text_from_xml(xml_data, 'status_whiteboard')
                ret_dict['good_for_newcomers'] = any(b in whiteboard_text for b in b_list)
            else:
                ret_dict['good_for_newcomers'] = False
        else:
            ret_dict['good_for_newcomers'] = False
        # Chemck whether this is a documentation bug.
        if documentation_type:
            d_list = documentation_text.split(',')
            if documentation_type == 'key':
                ret_dict['concerns_just_documentation'] = any(d in keywords for d in d_list)
            elif documentation_type == 'comp':
                ret_dict['concerns_just_documentation'] = any(d == self.component for d in d_list)
            elif documentation_type == 'prod':
                ret_dict['concerns_just_documentation'] = any(d == self.product for d in d_list)
            else:
                ret_dict['concerns_just_documentation'] = False
        else:
            ret_dict['concerns_just_documentation'] = False

        # If being called in a subclass, open ourselves up to some overriding
        self.extract_tracker_specific_data(xml_data, ret_dict)

        # And pass ret_dict on.
        return ret_dict

    def extract_tracker_specific_data(self, xml_data, ret_dict):
        pass # Override me

    def generate_bug_project_name(self, bug_project_name_format, tracker_name):
        return bug_project_name_format.format(
                tracker_name=tracker_name,
                product=self.product,
                component=self.component)

### Custom bug parsers
class GnomeBugzilla(BugzillaBugParser):
    def generate_bug_project_name(self, bug_project_name_format, tracker_name):
        bug_project_name = self.product
        gnome2openhatch = {'general': 'GNOME (general)',
                           'website': 'GNOME (website)'}
        if bug_project_name in gnome2openhatch:
            bug_project_name=gnome2openhatch[bug_project_name]
        return bug_project_name

class MozillaBugParser(BugzillaBugParser):
    def generate_bug_project_name(self, bug_project_name_format, tracker_name):
        ### Special-case the project names we know about
        mozilla2openhatch = {'Core': 'Mozilla Core',
                             'Firefox': 'Firefox',
                             'MailNews Core': 'Mozilla Messaging',
                             'addons.mozilla.org': 'addons.mozilla.org',
                             'Thunderbird': 'Thunderbird',
                             'Testing': 'Mozilla automated testing',
                             'Directory': 'Mozilla LDAP',
                             'mozilla.org': 'mozilla.org',
                             'SeaMonkey': 'SeaMonkey',
                             'Toolkit': 'Mozilla Toolkit',
                             'support.mozilla.com': 'support.mozilla.com',
                             'Camino': 'Camino',
                             'Calendar': 'Mozilla Calendar',
                             'Mozilla Localizations': 'Mozilla Localizations',
                             'Mozilla QA': 'Mozilla QA',
                             'Mozilla Services': 'Mozilla Services',
                             'Webtools': 'Mozilla Webtools',
                             'Input': 'Mozilla Input',
                             'Fennec': 'Fennec',
                             }
        if self.product == 'Other Applications':
            bug_project_name = 'Mozilla ' + self.component
        else:
            bug_project_name = mozilla2openhatch[self.product]
        return bug_project_name

class MediaWikiBugParser(BugzillaBugParser):
    def generate_bug_project_name(self, bug_project_name_format, tracker_name):
        product = self.product
        if product == 'MediaWiki extensions':
            bug_project_name = self.component
            if bug_project_name in ('FCKeditor', 'Gadgets'):
                bug_project_name += ' for MediaWiki'
        else:
            bug_project_name = product
        return bug_project_name

class KDEBugzilla(BugzillaBugParser):

    def extract_tracker_specific_data(self, xml_data, ret_dict):
        # Make modifications to ret_dict using provided metadata
        keywords_text = self.get_tag_text_from_xml(xml_data, 'keywords')
        keywords = map(lambda s: s.strip(),
                       keywords_text.split(','))
        ret_dict['good_for_newcomers'] = ('junior-jobs' in keywords)
        # Remove 'JJ:' from title if present
        if ret_dict['title'].startswith("JJ:"):
            ret_dict['title'] = ret_dict['title'][3:].strip()
        # Check whether documentation bug
        product = self.get_tag_text_from_xml(xml_data, 'product')
        ret_dict['concerns_just_documentation'] = (product == 'docs')
        # Then pass ret_dict back
        return ret_dict

    def generate_bug_project_name(self, bug_project_name_format, tracker_name):
        product = self.product
        reasonable_products = set([
            'Akonadi',
            'Phonon'
            'kmail',
            'Rocs',
            'akregator',
            'amarok',
            'ark',
            'cervisia',
            'k3b',
            'kappfinder',
            'kbabel',
            'kdeprint',
            'kdesktop',
            'kfile',
            'kfourinline',
            'khotkeys',
            'kio',
            'kmail',
            'kmplot',
            'koffice',
            'kompare',
            'konquerorr',
            'kopete',
            'kpat',
            'kphotoalbum',
            'krita',
            'ksmserver',
            'kspread',
            'ksysguard',
            'ktimetracker',
            'kwin',
            'kword',
            'marble',
            'okular',
            'plasma',
            'printer-applet',
            'rsibreak',
            'step',
            'systemsettings',
            'kdelibs',
            'kcontrol',
            'korganizer',
            'kipiplugins',
            'Phonon',
            'dolphin',
            'umbrello']
            )
        products_to_be_renamed = {
            'konqueror': 'boomski',
            'digikamimageplugins': 'digikam image plugins',
            'Network Management': 'KDE Network Management',
            'telepathy': 'telepathy for KDE',
            'docs': 'KDE documentation',
            }
        component = self.component
        things = (product, component)

        if product in reasonable_products:
            bug_project_name = product
        else:
            if product in products_to_be_renamed:
                bug_project_name = products_to_be_renamed[product]
            else:
                logging.info("Guessing on KDE subproject name. Found %s" %  repr(things))
                bug_project_name = product
        return bug_project_name
