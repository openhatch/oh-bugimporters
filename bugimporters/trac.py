# This file is part of OpenHatch.
# Copyright (C) 2010, 2011 Jack Grigg
# Copyright (C) 2010 OpenHatch, Inc.
# Copyright (C) 2012 Berry Phillips.
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

import cgi
import csv
import datetime
import feedparser
import lxml
import lxml.html
import twisted.web.error
import twisted.web.http
import urlparse
import logging
import StringIO


from bugimporters.base import BugImporter
from bugimporters.helpers import (string2naive_datetime, cached_property,
        unicodify_strings_when_inputted, wrap_file_object_in_utf8_check)
import bugimporters.items

class TracBugImporter(BugImporter):
    def __init__(self, *args, **kwargs):
        # Create a list to store bug ids obtained from queries.
        self.bug_ids = []
        # Call the parent __init__.
        super(TracBugImporter, self).__init__(*args, **kwargs)

    def process_queries(self, queries):
        # If this is an old Trac version, update the timeline.
        if self.tm.old_trac:
            pass
            ### FIXME: Ensure old_trac handling is covered in the
            ### test suite.

        # Add all the queries to the waiting list
        for query in queries:
            query_url = query.get_query_url()
            print query_url
            self.add_url_to_waiting_list(
                    url=query_url,
                    callback=self.handle_query_csv)
            query.last_polled = datetime.datetime.utcnow()
            query.save()

        # URLs are now all prepped, so start pushing them onto the reactor.
        self.push_urls_onto_reactor()

    def handle_timeline_rss(self, timeline_rss):
        # There are two steps to updating the timeline.
        # First step is to use the actual timeline to update the date_reported and
        # last_touched fields for each bug.

        # Parse the returned timeline RSS feed.
        for entry in feedparser.parse(timeline_rss).entries:
            # Format the data.
            base_url = self.tm.base_url
            entry_url = entry.link.rsplit("#", 1)[0]
            entry_date = datetime.datetime(*entry.date_parsed[0:6])
            entry_status = entry.title.split("): ", 1)[0].rsplit(" ", 1)[1]

            timeline_url = self.data_transits['trac']['get_timeline_url'](
                **locals())

            # Add the URL to the waiting list
            self.add_url_to_waiting_list(
                url=timeline_url,
                callback=self.handle_timeline_rss)

        # Second step is to use the RSS feed for each individual bug to update the
        # last_touched field. This would be unneccessary if the timeline showed
        # update events as well as creation and closing ones, and in fact later
        # versions of Trac have this option - but then the later versions of Trac
        # also hyperlink to the timeline from the bug, making this all moot.
        # Also, we cannot just use the RSS feed for everything, as it is missing
        # the date_reported time, as well as a lot of information about the bug
        # itself (e.g. Priority).
        for tb_times in self.timeline.tracbugtimes_set.all():
            # Check that the bug has not beeen seen as 'closed' in the timeline.
            # This will reduce network load by not grabbing the RSS feed of bugs
            # whose last_touched info is definitely correct.
            if 'closed' not in tb_times.latest_timeline_status:
                self.add_url_to_waiting_list(
                        url=tb_times.canonical_bug_link + '?format=rss',
                        callback=self.handle_bug_rss,
                        callback_args=tb_times)

        # URLs are now all prepped, so start pushing them onto the reactor.
        self.push_urls_onto_reactor()

    def handle_bug_rss(self, bug_rss, tb_times):
        feed = feedparser.parse(bug_rss)
        comment_dates = [datetime.datetime(
                *e.date_parsed[0:6]) for e in feed.entries]
        # Check if there are comments to grab from.
        if comment_dates:
            tb_times.last_polled = max(comment_dates)
            tb_times.save()

    def handle_query_csv(self, query_csv):
        # Remove any Unicode oddities before we process query_csv
        in_stream = StringIO.StringIO(query_csv)
        out_stream = wrap_file_object_in_utf8_check(in_stream)
        query_csv = out_stream.read()

        # If the "csv" starts with an HTML stanza, log that and die.
        if query_csv.lower().strip().startswith('<!doctype'):
            logging.error("We got HTML instead of actual CSV data.")
            return

        # Turn the string into a list so csv.DictReader can handle it.
        query_csv_list = query_csv.split('\n')
        dictreader = csv.DictReader(query_csv_list)
        bug_ids = []
        for line in dictreader:
            if 'id' in line:
                bug_ids.append(int(line['id']))
            else:
                logging.warning("Curious: We ran into a really odd line in Roundup.")
                logging.warning("%s", line)
        self.bug_ids.extend(bug_ids)

    def prepare_bug_urls(self):
        # Pull bug_ids our of the internal storage. This is done in case the
        # list is simultaneously being written to, in which case just copying
        # the entire thing followed by ddeleting the contents could lead to
        # lost IDs.
        bug_id_list = []
        while self.bug_ids:
            bug_id_list.append(self.bug_ids.pop())

        # Convert the obtained bug ids to URLs.
        bug_url_list = [urlparse.urljoin(self.tm.get_base_url(),
                                "ticket/%d" % bug_id) for bug_id in bug_id_list]

        # Get the sub-list of URLs that are fresh.
        fresh_bug_urls = self.data_transits['bug']['get_fresh_urls'](bug_url_list)

        # Remove the fresh URLs to be let with stale or new URLs.
        for bug_url in fresh_bug_urls:
            bug_url_list.remove(bug_url)

        # Put the bug list in the form required for process_bugs.
        # The second entry of the tuple is None as Trac never supplies
        # data via queries.
        bug_list = [(bug_url, None) for bug_url in bug_url_list]

        # And now go on to process the bug list
        self.process_bugs(bug_list)

    def process_bugs(self, bug_list):
        # If there are no bug URLs, finish now.
        if not bug_list:
            self.determine_if_finished()
            return

        for bug_url, _ in bug_list:
            # Create a TracBugParser instance to store the bug data
            tbp = TracBugParser(bug_url)

            self.add_url_to_waiting_list(
                    url=tbp.bug_csv_url,
                    callback=self.handle_bug_csv,
                    c_args={'tbp': tbp},
                    errback=self.errback_bug_data,
                    e_args={'tbp': tbp})

        # URLs are now all prepped, so start pushing them onto the reactor.
        self.push_urls_onto_reactor()

    def handle_bug_csv(self, bug_csv, tbp):
        # Pass the TracBugParser the CSV data
        tbp.set_bug_csv_data(bug_csv)

        # Now fetch the bug HTML
        self.add_url_to_waiting_list(
                url=tbp.bug_html_url,
                callback=self.handle_bug_html,
                c_args={'tbp': tbp},
                errback=self.errback_bug_data,
                e_args={'tbp': tbp})

    def errback_bug_data(self, failure, tbp):
        # For some unknown reason, some trackers choose to delete some bugs
        # entirely instead of just marking them as closed. That is fine for
        # bugs we haven't yet pulled, but if the bug is already being tracked
        # then we get a 404 error. This catcher looks for a 404 and deletes
        # the bug if it occurs.
        if failure.check(twisted.web.error.Error) and failure.value.status == \
                twisted.web.http.NOT_FOUND:
            self.data_transits['bug']['delete_by_url'](tbp.bug_url)
            # To keep the callback chain happy, explicity return None.
            return None
        elif failure.check(twisted.web.client.PartialDownloadError):
            # Log and squelch
            logging.warn(failure)
            return tbp
        else:
            # Pass the Failure on.
            return failure

    def handle_bug_html(self, bug_html, tbp):
        # Pass the TracBugParser the HTML data
        tbp.set_bug_html_data(bug_html)

        # Get the parsed data dict from the TracBugParser
        data = tbp.get_parsed_data_dict(self.tm)
        data['tracker'] = self.tm

        if self.tm.old_trac:

            # It's an old version of Trac that doesn't have links from the
            # bugs to the timeline. So we need to fetch these times from
            # the database built earlier.
            date_reported, last_touched = self.data_transits[
                    'trac']['get_bug_times'](tbp.bug_url)
            data.update({
                'date_reported': date_reported,
                'last_touched': last_touched,
                })

        self.data_transits['bug']['update'](data)

    def generate_bug_project_name(self, tbp):
        return self.tm.bug_project_name_format.format(
                tracker_name=self.tm.tracker_name, component=tbp.component)

    def determine_if_finished(self):
        # If we got here then there are no more URLs in the waiting list.
        # So if self.bug_ids is also empty then we are done.
        if self.bug_ids:
            self.prepare_bug_urls()
        else:
            self.finish_import()


class TracBugParser(object):
    @staticmethod
    def page2metadata_table(doc):
        ret = {}
        key_ths = doc.cssselect('table.properties th')
        for key_th in key_ths:
            key = key_th.text
            value = key_th.itersiblings().next().text
            if value is not None:
                ret[key.strip()] = value.strip()
        return ret

    @staticmethod
    def page2description_div(doc):
        div = doc.cssselect('.description .searchable')[0]
        cleaner = lxml.html.clean.Cleaner(javascript=True, scripts=True,
                meta=True, page_structure=True, embedded=True, frames=True,
                forms=True, remove_unknown_tags=True, safe_attrs_only=True,
                add_nofollow=True)
        return cleaner.clean_html(lxml.html.tostring(div))

    @staticmethod
    def page2date_opened(doc):
        span = doc.cssselect(
            '''.date p:contains("Opened") span,
            .date p:contains("Opened") a''')[0]
        return TracBugParser._span2date(span)

    @staticmethod
    def page2date_modified(doc):
        try:
            span = doc.cssselect(
                '''.date p:contains("Last modified") span,
                .date p:contains("Last modified") a''')[0]
        except IndexError:
            return TracBugParser.page2date_opened(doc)
        return TracBugParser._span2date(span)

    @staticmethod
    def _span2date(span):
        date_string = span.attrib['title']
        date_string = date_string.replace('in Timeline', '')
        date_string = date_string.replace('See timeline at ', '')
        return string2naive_datetime(date_string)

    @staticmethod
    def all_people_in_changes(doc):
        people = []
        for change_h3 in doc.cssselect('.change h3'):
            text = change_h3.text_content()
            for line in text.split('\n'):
                if 'changed by' in line:
                    person = line.split('changed by')[1].strip()
                    people.append(person)
        return people

    def __init__(self, bug_url):
        self.bug_csv = None
        self.bug_html = None
        self.bug_url = bug_url

    @cached_property
    def bug_html_url(self):
        return self.bug_url

    @cached_property
    def bug_csv_url(self):
        return '%s?format=csv' % self.bug_html_url

    @cached_property
    def component(self):
        try:
            return self.bug_csv['component']
        except KeyError:
            return ''

    def set_bug_csv_data(self, bug_csv):
        bug_csv_list = bug_csv.split('\n')
        dr = csv.DictReader(bug_csv_list)
        self.bug_csv = dr.next()

    def set_bug_html_data(self, bug_html):
        self.bug_html_as_bytes = bug_html
        self.bug_html = lxml.html.fromstring(bug_html)

    @staticmethod
    @unicodify_strings_when_inputted
    def string_un_csv(s):
        """Trac serializes bug descriptions. Undo that serialization."""
        s = cgi.escape(s)
        return s

    def get_parsed_data_dict(self, tm):
        # Note that this actually returns a scrapy.Item, which looks and
        # feels like a dict object, but has some special conveniences.
        #
        # Seems that some Trac bug trackers don't give all the information
        # below. For now, just put the offending item inside a try catch and
        # give it a null case.
        ret = bugimporters.items.ParsedBug()
        ret.update({'title': self.bug_csv['summary'],
               'description': TracBugParser.string_un_csv(
                        self.bug_csv['description']),
               'status': self.bug_csv['status'],
               'submitter_username': self.bug_csv['reporter'],
               'submitter_realname': '',  # can't find this in Trac
               'canonical_bug_link': self.bug_url,
               'last_polled': datetime.datetime.utcnow(),
               '_project_name': tm.tracker_name,
               })
        ret['importance'] = self.bug_csv.get('priority', '')

        ret['looks_closed'] = (self.bug_csv['status'] == 'closed')

        page_metadata = TracBugParser.page2metadata_table(self.bug_html)

        # Set as_appears_in_distribution.
        ret['as_appears_in_distribution'] = tm.as_appears_in_distribution

        if not page_metadata:
            logging.warn("This Trac bug got no page metadata. Probably we did"
                    " not find it on the page.")
            logging.warn("Bug URL: %s", self.bug_url)
            return ret

        all_people = set(TracBugParser.all_people_in_changes(self.bug_html))
        all_people.add(page_metadata['Reported by:'])
        all_people.update(
            map(lambda x: x.strip(),
                page_metadata.get('Cc', '').split(',')))
        all_people.update(
            map(lambda x: x.strip(),
                page_metadata.get('Cc:', '').split(',')))
        try:
            assignee = page_metadata['Assigned to:']
        except KeyError:
            try:
                assignee = page_metadata['Owned by:']
            except KeyError:
                assignee = ''
        if assignee:
            all_people.add(assignee)

        ret['people_involved'] = len(all_people)

        # FIXME: Need time zone
        if not tm.old_trac:
            # All is fine, proceed as normal.
            ret['date_reported'] = TracBugParser.page2date_opened(self.bug_html)
            ret['last_touched'] = TracBugParser.page2date_modified(self.bug_html)

        # Check for the bitesized keyword
        if tm.bitesized_type:
            b_list = tm.bitesized_text.split(',')
            ret['good_for_newcomers'] = any(
                    b in self.bug_csv[tm.bitesized_type] for b in b_list)
        else:
            ret['good_for_newcomers'] = False
        # Check whether this is a documentation bug.
        if tm.documentation_type:
            d_list = tm.documentation_text.split(',')
            ret['concerns_just_documentation'] = any(
                    d in self.bug_csv[tm.documentation_type] for d in d_list)
        else:
            ret['concerns_just_documentation'] = False

        # Then pass ret out
        return ret
