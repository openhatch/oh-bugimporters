# This file is part of OpenHatch.
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

import json
import datetime
import dateutil.parser
import logging
import scrapy.http

import bugimporters.items
from bugimporters.base import BugImporter


class LaunchpadBugImporter(BugImporter):
    """
    This class is a launchpad bug importer using the launchpad rest api.

    The api is documented at https://launchpad.net/+apidoc/ .

    We start with a query to get the bug_tasks for a project at
    https://api.launchpad.net/1.0/bzr?ws.op=searchTasks . This will be a
    pagnated collection of bug tasks.
    {
        'total_size': 1
        'next_collection_link': 'https://...', #  only included if there is a next page
        'entries': [{}]
    }
    The entries will be a list of
    https://launchpad.net/+apidoc/1.0.html#bug_task . The web_link on the
    bug_task will be used as the canonical_bug_link. We will need to make
    requests to the owner_link and the bug_link.

    The owner_link will return a https://launchpad.net/+apidoc/1.0.html#person .

    The bug_link will return a https://launchpad.net/+apidoc/1.0.html#bug .
    This bug will contain a subscriptions_collection_link on with the
    total_size can be used for the people_involved.
    """

    def __init__(self, *args, **kwargs):
        super(LaunchpadBugImporter, self).__init__(*args, **kwargs)

    def process_queries(self, queries):
        for query in queries:
            logging.debug('querying %s', query)
            r = scrapy.http.Request(
                url=query,
                callback=self.handle_bug_list_response)
            yield r

    def handle_bug_list_response(self, response):
        return self.handle_bug_list(response.body)

    def handle_bug_list(self, data):
        """
        Callback for a collection of bug_tasks.
        """
        logging.debug('handle_bug_list')
        bug_collection = json.loads(data)
        url = bug_collection.get('next_collection_link')
        if url:  # Get the next page
            yield scrapy.http.Request(
                url=url,
                callback=self.handle_bug_list_response)

        # The bug data that show up in bug_collection['entries']
        # is equivalent to what we get back if we asked for the
        # data on that bug explicitly.
        next_request = self.process_bugs([(bug['web_link'], bug) for
            bug in bug_collection['entries']])
        yield next_request

    def _convert_web_to_api(self, url):
        parts = url.split('/')
        project = parts[-3]
        bug_id = parts[-1]
        bug_api_url = 'https://api.launchpad.net/1.0/%s/+bug/%s' % (
            project, bug_id)
        return bug_api_url

    def process_bugs(self, bug_list):
        logging.debug('process_bugs')
        if not bug_list:
            return

        for bug_url, task_data in bug_list:
            lp_bug = LaunchpadBug(self.tm)
            if task_data:
                return self.handle_task_data_json(task_data, lp_bug)
            else:
                bug_api_url = self._convert_web_to_api(bug_url)
                r = scrapy.http.Request(
                    url=bug_api_url,
                    callback=self.handle_task_data)
                r.meta['lp_bug'] = lp_bug
                return r

    def handle_task_data(self, task_data, lp_bug):
        """
        Callback for a single bug_task.
        """
        logging.debug('handle_task_data')
        data = json.loads(task_data)
        return self.handle_task_data_json(data, lp_bug)

    def handle_task_data_json(self, data, lp_bug):
        """
        Process a single parsed bug_task.

        This can come from handle_task_data, or process_bugs.
        """
        if data['resource_type_link'] != 'https://api.launchpad.net/1.0/#bug_task':
            return

        lp_bug.parse_task(data)

        bug_url = data['bug_link']

        r = scrapy.http.Request(
            url=bug_url,
            callback=self.handle_bug_data_response)
        r.meta['lp_bug'] = lp_bug
        return r

    def handle_bug_data_response(self, response):
        return self.handle_bug_data(response.body,
                                    response.meta['lp_bug'])

    def handle_bug_data(self, bug_data, lp_bug):
        """
        Callback for a bug.
        """
        logging.debug('handle_bug_data')
        data = json.loads(bug_data)
        lp_bug.parse_bug(data)

        sub_url = data['subscriptions_collection_link']
        r = scrapy.http.Request(
            url=sub_url,
            callback=self.handle_subscriptions_response)
        r.meta['lp_bug'] = lp_bug
        return r

    def handle_subscriptions_response(self, response):
        return self.handle_subscriptions_data(response.body,
                                              response.meta['lp_bug'])

    def handle_subscriptions_data(self, sub_data, lp_bug):
        """
        Callback for collection of bug_subscription.
        """
        logging.debug('handle_subscriptions_data')
        data = json.loads(sub_data)
        lp_bug.parse_subscriptions(data)

        r = scrapy.http.Request(
            url=lp_bug.owner_link,
            callback=self.handle_user_response)
        r.meta['lp_bug'] =  lp_bug
        return r

    def handle_user_response(self, response):
        return self.handle_user_data(response.body,
                                     response.meta['lp_bug'])

    def handle_user_data(self, user_data, lp_bug):
        """
        Callback for person.
        """
        logging.debug('handle_user_data')
        data = json.loads(user_data)
        lp_bug.parse_user(data)

        full_data = lp_bug.get_data()

        full_data.update({
            'canonical_bug_link': lp_bug.url,
            '_tracker_name': self.tm.tracker_name
        })

        return bugimporters.items.ParsedBug(full_data)

class LaunchpadBug(object):
    def __init__(self, tracker):
        self._tracker = tracker
        self._data = bugimporters.items.ParsedBug()
        self._data['last_polled'] = datetime.datetime.utcnow().isoformat()

    def _parse_datetime(self, ts):
        return dateutil.parser.parse(ts).replace(tzinfo=None)

    def parse_task(self, data):
        self.url = data['web_link']
        self._data['status'] = data['status']
        self._data['date_reported'] = self._parse_datetime(data['date_created']).isoformat()
        self._data['title'] = data['title']
        self._data['importance'] = data['importance']
        self._data['canonical_bug_link'] = data['web_link']
        self._data['looks_closed'] = bool(data['date_closed'])

    def parse_bug(self, data):
        self.owner_link = data['owner_link']
        self._data['last_touched'] = self._parse_datetime(data['date_last_updated']).isoformat()
        self._data['_project_name'] = self._tracker.tracker_name
        self._data['description'] = data['description']
        self._data['concerns_just_documentation'] = \
            self._tracker.documentation_tag in data['tags']
        self._data['good_for_newcomers'] = \
            self._tracker.bitesized_tag in data['tags']

    def parse_subscriptions(self, data):
        self._data['people_involved'] = int(data['total_size'])

    def parse_user(self, data):
        self._data['submitter_username'] = data['name']
        self._data['submitter_realname'] = data['display_name']

    def copy_to_bug(self, bug):
        for k, v in self._data.items():
            setattr(bug, k, v)

    def get_data(self):
        return dict(self._data)
