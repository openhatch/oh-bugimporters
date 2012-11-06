# This file is part of OpenHatch.
# Copyright (C) 2012 John Morrissey
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
import importlib
import json
import scrapy.http
import scrapy.spider

import bugimporters.items
from bugimporters.base import BugImporter, printable_datetime
from bugimporters.helpers import string2naive_datetime

class GitHubBugImporter(BugImporter):
    def process_queries(self, queries):
        for query in queries:
            yield scrapy.http.Request(
                url=query,
                callback=self.handle_bug_list_response)

    def handle_bug_list_response(self, response):
        issue_list = json.loads(response.body)

        for bug in issue_list:
            yield self.handle_bug(bug)

    def process_bugs(self, bug_list):
        for bug_url, bug_data in bug_list:
            r = scrapy.http.Request(
                url=bug_url,
                callback=self.handle_bug_show_response)
            yield r

    def handle_bug_show_response(self, response):
        bug_data = json.loads(response.body)
        return self.handle_bug(bug_data)

    def handle_bug(self, bug_data):
        gbp = GitHubBugParser(self.tm, self.tm.github_name,
            self.tm.github_repo)
        return gbp.parse(bug_data)

class GitHubBugParser(object):
    def __init__(self, tm, github_name, github_repo):
        self.tm = tm
        self.github_name = github_name
        self.github_repo = github_repo

    @staticmethod
    def github_count_people_involved(issue):
        # The reporter counts as a person.
        people = 1

        if (issue['assignee'] and
            issue['assignee']['login'] != issue['user']['login']):
            people += 1

        if issue['comments'] > 0:
            # FIXME: pull comments to get an accurate count; for now,
            # we'll just bump the involved people count even though
            # the commenter might be the reporting user.
            people += 1

        return people

    def parse(self, issue):
        parsed = bugimporters.items.ParsedBug({
            'title': issue['title'],
            'description': issue['body'],
            'status': issue['state'],
            'people_involved': self.github_count_people_involved(issue),
            'date_reported': printable_datetime(string2naive_datetime(issue['created_at'])),
            'last_touched': printable_datetime(string2naive_datetime(issue['updated_at'])),
            'submitter_username': issue['user']['login'],
            'submitter_realname': '', # FIXME: can get this from ['user']['url']
            'canonical_bug_link': issue['html_url'],
            'looks_closed': (issue['state'] == 'closed'),
            'last_polled': printable_datetime(),
            '_project_name': self.tm.tracker_name,
            '_tracker_name': self.tm.tracker_name,
        })

        issue_labels = set([
            l['name'] for l in issue['labels']
        ])

        b_list = self.tm.bitesized_tag.split(',')
        parsed['good_for_newcomers'] = not issue_labels.isdisjoint(b_list)

        d_list = self.tm.documentation_tag.split(',')
        parsed['concerns_just_documentation'] = not issue_labels.isdisjoint(d_list)

        return parsed
