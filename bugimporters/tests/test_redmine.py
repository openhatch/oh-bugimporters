import autoresponse
import datetime
import os
from urllib import urlencode

from bugimporters.base import printable_datetime
from bugimporters.redmine import RedmineBugImporter
import bugimporters.main
from bugimporters.tests import TrackerModel

HERE = os.path.dirname(os.path.abspath(__file__))

class TestRedmineBugImporter(object):

    @staticmethod
    def assertEqual(x, y):
        assert x == y

    def setup_class(self):
        self.tm = TrackerModel()
        self.im = RedmineBugImporter(self.tm)

    def test_top_to_bottom_open(self):
        spider = bugimporters.main.BugImportSpider()
        self.tm.bugimporter = 'redmine.RedmineBugImporter'
        self.tm.tracker_name = 'openhatch tests'
        self.tm.base_url = 'http://dev.cfengine.com/'
        self.tm.bitesized_text = 'bitesize'
        self.tm.documentation_text = 'docs'
        self.tm.queries = [
            'https://dev.cfengine.com/issues.json'
        ]
        spider.input_data = [self.tm.__dict__]

        url2filename = {
            'https://dev.cfengine.com/issues.json':
                os.path.join(HERE, 'sample-data', 'redmine', 'issue-list'),
            'https://dev.cfengine.com/issues.json?limit=1&offset=1':
                os.path.join(HERE, 'sample-data', 'redmine', 'issue-list-paginated'),
        }
        ar = autoresponse.Autoresponder(url2filename=url2filename,
                                        url2errors={})

        bugs = ar.respond_recursively(spider.start_requests())
        assert len(bugs) == 2

        bug = bugs[0]
        self.assertEqual(bug['title'], 'A bug')
        self.assertEqual(bug['description'], "foo bar baz")
        self.assertEqual(bug['status'], 'Open')
        self.assertEqual(bug['date_reported'],
                printable_datetime(datetime.datetime(2015, 04, 29,
            21, 40, 20, 0)))
        self.assertEqual(bug['last_touched'], printable_datetime(datetime.datetime(2015, 04, 29, 21, 41, 4,
                    0)))
        self.assertEqual(bug['submitter_username'], '')
        self.assertEqual(bug['submitter_realname'], 'William Orr')
        self.assertEqual(bug['canonical_bug_link'], 'http://dev.cfengine.com//issues/7137')
        self.assertEqual(bug['good_for_newcomers'], True)
        self.assertEqual(bug['concerns_just_documentation'], False)
        self.assertEqual(bug['looks_closed'], False)


    def test_top_to_bottom_closed(self):
        spider = bugimporters.main.BugImportSpider()
        self.tm.bugimporter = 'redmine.RedmineBugImporter'
        self.tm.tracker_name = 'openhatch tests'
        self.tm.base_url = 'http://dev.cfengine.com/'
        self.tm.bitesized_text = 'bitesize'
        self.tm.documentation_text = 'docs'
        self.tm.queries = [
            'https://dev.cfengine.com/issues.json?status_id=closed'
        ]
        spider.input_data = [self.tm.__dict__]

        url2filename = {
            'https://dev.cfengine.com/issues.json?status_id=closed':
                os.path.join(HERE, 'sample-data', 'redmine', 'issue-list-closed'),
        }
        ar = autoresponse.Autoresponder(url2filename=url2filename,
                                        url2errors={})

        bugs = ar.respond_recursively(spider.start_requests())
        assert len(bugs) == 1

        bug = bugs[0]
        self.assertEqual(bug['title'], 'A bug')
        self.assertEqual(bug['description'], "foo bar baz")
        self.assertEqual(bug['status'], 'Closed')
        self.assertEqual(bug['date_reported'],
                printable_datetime(datetime.datetime(2015, 4, 16,
            8, 11, 18, 0)))
        self.assertEqual(bug['last_touched'], printable_datetime(datetime.datetime(2015, 4, 27, 7, 55, 37,
                    0)))
        self.assertEqual(bug['submitter_username'], '')
        self.assertEqual(bug['submitter_realname'], 'William Orr')
        self.assertEqual(bug['canonical_bug_link'], 'http://dev.cfengine.com//issues/7111')
        self.assertEqual(bug['good_for_newcomers'], False)
        self.assertEqual(bug['concerns_just_documentation'], False)
        self.assertEqual(bug['looks_closed'], True)

    def test_process_bugs(self):
        spider = bugimporters.main.BugImportSpider()
        self.tm.bugimporter = 'redmine.RedmineBugImporter'
        self.tm.tracker_name = 'openhatch tests'
        self.tm.base_url = 'http://dev.cfengine.com/'
        self.tm.bitesized_text = 'bitesize'
        self.tm.documentation_text = 'docs'
        self.tm.get_older_bug_data = ('http://dev.cfengine.com/issues.json?status_id=*&created_on=>=2014-01-02T08:12:32Z')
        self.tm.queries = []
        self.tm.existing_bug_urls = [
            'http://dev.cfengine.com//issues/7137'
        ]
        spider.input_data = [self.tm.__dict__]

        url2filename = {
                'http://dev.cfengine.com/issues.json?status_id=*&created_on=%3E=2014-01-02T08:12:32Z':
                    os.path.join(HERE, 'sample-data', 'redmine',
                        'issue-list-with-date-constraint')
                    }
        ar = autoresponse.Autoresponder(url2filename=url2filename,
                                        url2errors={})

        bugs = ar.respond_recursively(spider.start_requests())
        assert len(bugs) == 1


        bug = bugs[0]
        self.assertEqual(bug['canonical_bug_link'],
                self.tm.existing_bug_urls[0])
