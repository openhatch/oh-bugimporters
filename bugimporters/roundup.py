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

import datetime
import logging
import lxml
import re
import urlparse
import scrapy.http

try:
    from unicodecsv import DictReader
except ImportError:
    from unicodecsv import UnicodeDictReader as DictReader

import bugimporters.items
from bugimporters.helpers import cached_property
from bugimporters.base import BugImporter


class RoundupBugImporter(BugImporter):

    def __init__(self, *args, **kwargs):
        super(RoundupBugImporter, self).__init__(*args, **kwargs)
        # Call the parent __init__.

    def process_queries(self, queries):
        # Add all the queries to the waiting list
        for query in queries:
            query_url = query.get_query_url()
            yield scrapy.http.Request(url=query_url,
                    callback=self.handle_query_csv_response)

    def handle_query_csv_response(self, response):
        return self.handle_query_csv(response.body)

    def handle_query_csv(self, query_csv):
        # Turn the string into a list so csv.DictReader can handle it.
        query_csv_list = query_csv.split('\n')
        dictreader = DictReader(query_csv_list)
        bug_ids = [int(line['id']) for line in dictreader]
        return self.prepare_bug_urls(bug_ids)

    def prepare_bug_urls(self, bug_ids):
        # Convert the obtained bug ids to URLs.
        bug_url_list = [urlparse.urljoin(self.tm.get_base_url(),
                                "issue%d" % bug_id) for bug_id in bug_ids]

        # Put the bug list in the form required for process_bugs.
        # The second entry of the tuple is None as Roundup never supplies data
        # via queries.
        bug_list = [(bug_url, None) for bug_url in bug_url_list]

        # And now go on to process the bug list
        return self.process_bugs(bug_list)

    def process_bugs(self, bug_list):
        for bug_url, _ in bug_list:
            r = scrapy.http.Request(
                url=bug_url,
                callback=self.handle_bug_html_response)
            yield r

    def handle_bug_html_response(self, response):
        # Create a RoundupBugParser instance to store the bug data
        rbp = RoundupBugParser(response.request.url)
        return self.handle_bug_html(response.body, rbp)

    def handle_bug_html(self, bug_html, rbp):
        # Pass the RoundupBugParser the HTML data.
        rbp.set_bug_html_data(bug_html)

        # Get the parsed data dict from the RoundupBugParser.
        data = rbp.get_parsed_data_dict(self.tm)
        data.update({
            'canonical_bug_link': rbp.bug_url,
            '_tracker_name': self.tm.tracker_name
        })

        return bugimporters.items.ParsedBug(data)


class RoundupBugParser(object):
    def __init__(self, bug_url):
        self.bug_html = None
        self.bug_url = bug_url

    @cached_property
    def bug_html_url(self):
        return self.bug_url

    def set_bug_html_data(self, bug_html):
        self.bug_html = lxml.html.document_fromstring(bug_html)

    @staticmethod
    def roundup_tree2metadata_dict(tree):
        '''
        Input: tree is a parsed HTML document that lxml.html can understand.

        Output: For each <th>key</th><td>value</td> in the tree,
        append {'key': 'value'} to a dictionary.
        Return the dictionary when done.'''

        ret = {}
        for th in tree.cssselect('th'):
            # Get next sibling
            key_with_colon = th.text_content().strip()
            key = key_with_colon.rsplit(':', 1)[0]
            try:
                td = th.itersiblings().next()
            except StopIteration:
                # If there isn't an adjacent TD, don't use this TH.
                continue
            value = td.text_content().strip()
            ret[key] = value

        return ret

    def get_all_submitter_realname_pairs(self, tree):
        '''Input: the tree
        Output: A dictionary mapping username=>realname'''

        ret = {}
        for th in tree.cssselect('th'):
            match = re.match("Author: (([^(]*) \()?([^)]*)", th.text_content().strip())
            if match:
                _, realname, username = match.groups()
                ret[username] = realname
        return ret

    def get_submitter_realname(self, tree, submitter_username):
        try:
            return self.get_all_submitter_realname_pairs(tree)[submitter_username]
        except KeyError:
            return None

    def str2datetime_obj(self, date_string, possibility_index=0):
        # FIXME: I make guesses as to the timezone.
        possible_date_strings = [
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d.%H:%M",
                "%Y-%m-%d.%H:%M:%S"]
        try:
            return datetime.datetime.strptime(date_string, possible_date_strings[possibility_index])
        except ValueError:
            # A keyerror raised here means we ran out of a possibilities.
            return self.str2datetime_obj(date_string, possibility_index=possibility_index + 1)

    def get_parsed_data_dict(self, tm):
        metadata_dict = RoundupBugParser.roundup_tree2metadata_dict(self.bug_html)

        data = [
                x.text_content() for x in self.bug_html.cssselect(
                    'form[name=itemSynopsis] + p > b, form[name=itemSynopsis] + hr + p > b, ' +
                    'form[name=itemSynopsis] + p > strong, form[name=itemSynopsis] + hr + p > strong')]
        if len(data) > 4:
            if data[-1] == metadata_dict['Status']:
                data = data[:4]
        try:
            date_reported, submitter_username, last_touched, last_toucher = data
        except ValueError:
            date_reported, submitter_username, last_touched, last_toucher = data
            logging.error("Big problem parsing some Roundup data.")
            logging.error("It was: %s", data)
            date_reported, submitter_username, last_touched, last_toucher = [None] * 4

        # For description, just grab the first "message"
        try:
            description = self.bug_html.cssselect('table.messages td.content')[0].text_content().strip()
        except IndexError:
            # This Roundup issue has no messages.
            description = ""

        # Create a lookup set where all the values in here represent
        # status values that "look closed"
        closed_status_set = set()
        for status_name in tm.closed_status.split(','):
            closed_status_set.add(status_name.strip().lower())

        ret = bugimporters.items.ParsedBug()
        ret.update({'title': metadata_dict['Title'],
               'description': description,
               'importance': metadata_dict['Priority'],
               'status': metadata_dict['Status'],
               'looks_closed': (metadata_dict['Status'].lower() in closed_status_set),
               'submitter_username': submitter_username,
               'submitter_realname': self.get_submitter_realname(
                   self.bug_html,
                   submitter_username),
               'people_involved': len(self.get_all_submitter_realname_pairs(self.bug_html)),
               'date_reported': self.str2datetime_obj(date_reported).isoformat(),
               'last_touched': self.str2datetime_obj(last_touched).isoformat(),
               'canonical_bug_link': self.bug_url,
               'last_polled': datetime.datetime.utcnow().isoformat(),
               '_project_name': tm.tracker_name,
               })

        # Check for the bitesized keyword
        if tm.bitesized_field:
            b_list = tm.bitesized_text.split(',')
            ret['good_for_newcomers'] = any(b in metadata_dict.get(tm.bitesized_field, '') for b in b_list)
        else:
            ret['good_for_newcomers'] = False
        # Check whether this is a documentation bug.
        if tm.documentation_field:
            d_list = tm.documentation_text.split(',')
            ret['concerns_just_documentation'] = any(d in metadata_dict.get(tm.documentation_field, '') for d in d_list)
        else:
            ret['concerns_just_documentation'] = False

        # Set as_appears_in_distribution.
        ret['as_appears_in_distribution'] = tm.as_appears_in_distribution

        # Then pass ret out
        return ret
