# This file is part of OpenHatch
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

import json
import scrapy.http
import scrapy.spider

import bugimporters.items
from bugimporters.base import BugImporter, printable_datetime
from bugimporters.helpers import string2naive_datetime
from urlparse import urljoin

class JiraBugImporter(BugImporter):
    def process_queries(self, queries):
        for query in queries:
            yield scrapy.http.Request(
                url=query,
                callback=self.handle_bug_list_response)

    def handle_bug_list_response(self, response):
        issue_list = json.loads(response.body)

        for bug in issue_list['issues']:
            yield self.handle_bug(bug)


    def process_bugs(self, bug_list, older_bug_data_url):
        r = scrapy.http.Request(
            url=older_bug_data_url,
            callback=self.handle_old_bug_query)
        # For historical reasons, bug_list is a tuple of (url, data).
        # We just want the URLs.
        r.meta['bug_list'] = [url for (url, data) in bug_list]
        yield r

    def handle_old_bug_query(self, response):
        bugs_we_care_about = response.meta['bug_list']
        bugs_from_response = json.loads(response.body)["issues"]
        for bug in bugs_from_response:
            if bug['self'] in bugs_we_care_about:
                yield self.handle_bug(bug)

    def handle_bug_show_response(self, response):
        bug_data = json.loads(response.body)
        return self.handle_bug(bug_data)

    def handle_bug(self, bug_data):
        jbp = JiraBugParser(self.tm)
        return jbp.parse(bug_data)

class JiraBugParser(object):
    def __init__(self, tm):
        self.tm = tm

    def parse(self, issue):
        print "Tracker: ", self.tm
        parsed = bugimporters.items.ParsedBug({
            'title': issue['fields']['summary'],
            'description': issue['fields']['description'],
            'status': issue['fields']['status']['name'].lower(),
            'date_reported': printable_datetime(string2naive_datetime(issue['fields']['created'])),
            'last_touched': printable_datetime(string2naive_datetime(issue['fields']['updated'])),
            'submitter_username': issue['fields']['reporter']['name'],
            'submitter_realname': issue['fields']['reporter']['displayName'],
            'canonical_bug_link': urljoin(self.tm.get_base_url(), '/browse/' + issue['key']),
            'looks_closed': (issue['fields']['status']['name'] == 'Closed'),
            'last_polled': printable_datetime(),
            '_project_name': self.tm.tracker_name,
            '_tracker_name': self.tm.tracker_name,
        })

        issue_labels = set([
            l for l in issue['fields']['labels']
        ])
        if self.tm.bitesized_type:
            if self.tm.bitesized_type == 'label':
                b_list = self.tm.bitesized_text.split(',')
                parsed['good_for_newcomers'] = not issue_labels.isdisjoint(b_list)
            elif self.tm.bitesized_type == 'priority':
                parsed['good_for_newcomers'] = issue['fields']['priority']['name'] == self.tm.bitesized_text
            else:
                parsed['good_for_newcomers'] = False

        d_list = self.tm.documentation_text.split(',')
        parsed['concerns_just_documentation'] = not issue_labels.isdisjoint(d_list)

        return parsed
