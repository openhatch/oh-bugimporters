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
import json
import logging

import bugimporters.items
from bugimporters.base import BugImporter
from bugimporters.helpers import string2naive_datetime


class GitHubBugImporter(BugImporter):
    def process_queries(self, queries):
        for query in queries:
            url = query.get_query_url()

            logging.debug('querying %s', url)
            self.add_url_to_waiting_list(
                url=url,
                callback=self.handle_bug_list)

            query.last_polled = datetime.datetime.utcnow()
            query.save()

        self.push_urls_onto_reactor()

    def handle_bug_list(self, data):
        """
        Callback for a collection of bugs.
        """
        issue_list = json.loads(data)

        for bug in issue_list['issues']:
            self.handle_bug_json(bug)

    def process_bugs(self, bug_list):
        logging.debug('process_bugs')
        if not bug_list:
            self.determine_if_finished()
            return

        for bug_url, bug_data in bug_list:
            logging.debug('querying %s', bug_url)
            self.add_url_to_waiting_list(
                url=bug_url,
                callback=self.handle_bug_show)

        self.push_urls_onto_reactor()

    def handle_bug_show(self, data):
        self.handle_bug_json(json.loads(data)['issue'])

    def handle_bug_json(self, bug_json):
        gbp = self.bug_parser(self.tm, self.tm.github_name, self.tm.github_repo)

        data = gbp.parse(bug_json)
        data.update({
            'tracker': self.tm
        })

        self.data_transits['bug']['update'](data)

    def determine_if_finished(self):
        logging.debug('determine_if_finished')
        self.finish_import()

class GitHubBugParser(object):
    def __init__(self, tm, github_name, github_repo):
        self.tm = tm
        self.github_name = github_name
        self.github_repo = github_repo

    @staticmethod
    def github_date_to_datetime(date_string):
        return string2naive_datetime(date_string)

    @staticmethod
    def github_count_people_involved(issue):
        if issue['comments'] == 0:
            # FIXME: what about assignment?
            return 1

        # FIXME: pull comments to get an accurate count
        return 1

    def parse(self, issue):
        parsed = bugimporters.items.ParsedBug({
            'title': issue['title'],
            'description': issue['body'],
            'status': issue['state'],
            'people_involved': self.github_count_people_involved(issue),
            'date_reported': self.github_date_to_datetime(issue['created_at']),
            'last_touched': self.github_date_to_datetime(issue['updated_at']),
            'submitter_username': issue['user'],
            'submitter_realname': '', # FIXME: can't get this from GitHub?
            'canonical_bug_link':
                'http://github.com/api/v2/json/issues/show/%s/%s/%d' % (
                    self.github_name, self.github_repo, issue['number'],
                ),
            'looks_closed': (issue['state'] == 'closed'),
            '_project_name': self.tm.tracker_name,
        })

        b_list = self.tm.bitesized_tag.split(',')
        parsed['good_for_newcomers'] = any(b in issue['labels'] for b in b_list)

        d_list = self.tm.documentation_tag.split(',')
        parsed['concerns_just_documentation'] = any(d in issue['labels'] for d in d_list)

        return parsed
