import autoresponse
import datetime
import os

from bugimporters.base import printable_datetime
from bugimporters.jira import JiraBugImporter
import bugimporters.main
from bugimporters.tests import TrackerModel

HERE = os.path.dirname(os.path.abspath(__file__))

class TestJiraBugImporter(object):

    @staticmethod
    def assertEqual(x, y):
        assert x == y

    def setup_class(self):
        self.tm = TrackerModel()
        self.im = JiraBugImporter(self.tm)

    def test_top_to_bottom_open(self):
        spider = bugimporters.main.BugImportSpider()
        self.tm.bugimporter = 'jira.JiraBugImporter'
        self.tm.tracker_name = 'openhatch tests'
        self.tm.base_url = 'http://jira.cyanogenmod.org/browse/'
        self.tm.bitesized_type = 'label'
        self.tm.bitesized_text = 'bitesize'
        self.tm.documentation_text = 'docs'
        self.tm.queries = [
            'https://jira.cyanogenmod.org/rest/api/2/search?jql=status=open'
        ]
        spider.input_data = [self.tm.__dict__]

        url2filename = {
            'https://jira.cyanogenmod.org/rest/api/2/search?jql=status=open':
                os.path.join(HERE, 'sample-data', 'jira', 'issue-list'),
        }
        ar = autoresponse.Autoresponder(url2filename=url2filename,
                                        url2errors={})

        bugs = ar.respond_recursively(spider.start_requests())
        assert len(bugs) == 1

        bug = bugs[0]
        self.assertEqual(bug['title'], 'First Test Issue')
        self.assertEqual(bug['description'], "A description")
        self.assertEqual(bug['status'], 'open')
        self.assertEqual(bug['date_reported'],
                printable_datetime(datetime.datetime(2011, 11, 21,
            22, 22, 59, 899000)))
        self.assertEqual(bug['last_touched'], printable_datetime(datetime.datetime(2011, 11, 21, 22, 23, 2,
                    302000)))
        self.assertEqual(bug['submitter_username'], 'admin')
        self.assertEqual(bug['submitter_realname'], 'Administrator')
        self.assertEqual(bug['canonical_bug_link'],
                'http://jira.cyanogenmod.org/browse/MKY-1')
        self.assertEqual(bug['good_for_newcomers'], False)
        self.assertEqual(bug['concerns_just_documentation'], False)
        self.assertEqual(bug['looks_closed'], False)


    def test_top_to_bottom_closed(self):
        spider = bugimporters.main.BugImportSpider()
        self.tm.bugimporter = 'jira.JiraBugImporter'
        self.tm.tracker_name = 'openhatch tests'
        self.tm.base_url = 'http://jira.cyanogenmod.org/browse/'
        self.tm.bitesized_type = 'priority'
        self.tm.bitesized_text = 'Trivial'
        self.tm.documentation_text = 'docs'
        self.tm.queries = [
            'https://jira.cyanogenmod.org/rest/api/2/search?jql=status=closed'
        ]
        spider.input_data = [self.tm.__dict__]

        url2filename = {
            'https://jira.cyanogenmod.org/rest/api/2/search?jql=status=closed':
                os.path.join(HERE, 'sample-data', 'jira', 'issue-list-closed'),
        }
        ar = autoresponse.Autoresponder(url2filename=url2filename,
                                        url2errors={})

        bugs = ar.respond_recursively(spider.start_requests())
        assert len(bugs) == 1

        bug = bugs[0]
        self.assertEqual(bug['title'], 'First Test Issue')
        self.assertEqual(bug['description'], "A description")
        self.assertEqual(bug['status'], 'closed')
        self.assertEqual(bug['date_reported'],
                printable_datetime(datetime.datetime(2011, 11, 21,
            22, 22, 59, 899000)))
        self.assertEqual(bug['last_touched'], printable_datetime(datetime.datetime(2011, 11, 21, 22, 23, 2,
                    302000)))
        self.assertEqual(bug['submitter_username'], 'admin')
        self.assertEqual(bug['submitter_realname'], 'Administrator')
        self.assertEqual(bug['canonical_bug_link'],
                'http://jira.cyanogenmod.org/browse/MKY-1')
        self.assertEqual(bug['good_for_newcomers'], True)
        self.assertEqual(bug['concerns_just_documentation'], True)
        self.assertEqual(bug['looks_closed'], True)


    def test_process_bugs(self):
        spider = bugimporters.main.BugImportSpider()
        self.tm.bugimporter = 'jira.JiraBugImporter'
        self.tm.tracker_name = 'openhatch tests'
        self.tm.base_url = 'http://jira.cyanogenmod.org/browse/'
        self.tm.bitesized_text = 'bitesize'
        self.tm.documentation_text = 'docs'
        self.tm.queries = []
        self.tm.get_older_bug_data = ('http://jira.cyanogenmod.org/rest/api/2/search?jql=created>2011-12-08')
        self.tm.existing_bug_urls = [
            'http://jira.cyanogenmod.org/browse/CYAN-1']
        spider.input_data = [self.tm.__dict__]

        url2filename = {
                'http://jira.cyanogenmod.org/rest/api/2/search?jql=created%3E2011-12-08':
                    os.path.join(HERE, 'sample-data', 'jira',
                        'issue-list-with-date-constraint')
                    }
        ar = autoresponse.Autoresponder(url2filename=url2filename,
                                        url2errors={})

        bugs = ar.respond_recursively(spider.start_requests())
        self.assertEqual(len(bugs), 1)


        bug = bugs[0]
        self.assertEqual(bug['canonical_bug_link'],
                self.tm.existing_bug_urls[0])
