# This file is part of OpenHatch.
# Copyright (C) 2015 William Orr <will@worrbase.com>
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
from urllib import quote, urlencode

def redmine_generate_uri(bug, tm):
    return "{0}/issues/{1}".format(tm.get_base_url(), quote(str(bug["id"])))

class RedmineBugImporter(BugImporter):
    def process_queries(self, queries):
        for query in queries:
            yield scrapy.http.Request(
                url=query,
                callback=lambda response: self.handle_bug_list_response(query, response))

    def handle_bug_list_response(self, query, response):
        data = json.loads(response.body)
        if "issues" in data:
            if len(data["issues"]) + data["offset"] == data["limit"]:
                params = urlencode([("limit", data["limit"]),
                                    ("offset", data["limit"] + data["offset"])])
                url = "{0}?{1}".format(query, params)
                yield scrapy.http.Request(
                    url=url,
                    callback=lambda response: self.handle_bug_list_response(query, response))

            for issue in data["issues"]:
                yield self.handle_bug(issue)

    def process_bugs(self, bug_list, older_bug_data_url):
        r = scrapy.http.Request(
            url=older_bug_data_url,
            callback=self.handle_old_bug_query)
        r.meta['bug_list'] = [url for (url, _) in bug_list]
        yield r

    def handle_old_bug_query(self, response):
        bugs_we_care_about = response.meta['bug_list']
        bugs_from_response = json.loads(response.body)["issues"]
        for bug in bugs_from_response:
            if redmine_generate_uri(bug, self.tm) in bugs_we_care_about:
                yield self.handle_bug(bug)

    def handle_bug(self, bug):
        parser = RedmineBugParser(self.tm)
        return parser.parse(bug)

class RedmineBugParser(object):
    def __init__(self, tm):
        self._tm = tm

    @staticmethod
    def redmine_count_people_involved(bug):
        people = 1
        if bug["assigned_to"]:
            people += 1
        # FIXME: there isn't a good way to get the set of people involved in a ticket
        # in redmine right now
        return people

    @staticmethod
    def redmine_get_easy(bug, tm):
        fields = bug["custom_fields"]
        try:
            [field for field in fields if field["value"] == tm.bitesized_text][0]
            return True
        except IndexError:
            return False

    def parse(self, bug):
        return bugimporters.items.ParsedBug({
            "title": bug["subject"],
            "description": bug["description"],
            "status": bug["status"]["name"],
            "date_reported": printable_datetime(string2naive_datetime(bug["created_on"])),
            "last_touched": printable_datetime(string2naive_datetime(bug["updated_on"])),
            "submitter_username": "",
            "submitter_realname": bug["author"]["name"],
            "canonical_bug_link": redmine_generate_uri(bug, self._tm),
            "last_polled": printable_datetime(),
            "looks_closed": (bug["status"]["name"] == "Closed"),
            "_tracker_name": self._tm.tracker_name,
            "_project_name": self._tm.tracker_name,
            "concerns_just_documentation": (bug["tracker"]["name"] == "Documentation"),
            "people_involved": self.redmine_count_people_involved(bug),
            "good_for_newcomers": self.redmine_get_easy(bug, self._tm),
        })
