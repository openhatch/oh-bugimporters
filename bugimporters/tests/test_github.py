import autoresponse
import datetime
import os

from bugimporters.base import printable_datetime
from bugimporters.github import GitHubBugImporter
import bugimporters.main
from bugimporters.tests import ReactorManager, TrackerModel


HERE = os.path.dirname(os.path.abspath(__file__))

class TestGitHubBugImporter(object):
    @staticmethod
    def assertEqual(x, y):
        assert x == y

    def setup_class(cls):
        cls.tm = TrackerModel()
        cls.im = GitHubBugImporter(cls.tm, ReactorManager())

    def test_top_to_bottom_open(self):
        spider = bugimporters.main.BugImportSpider()
        self.tm.bugimporter = 'github.GitHubBugImporter'
        self.tm.tracker_name = 'openhatch tests'
        self.tm.github_name = 'openhatch'
        self.tm.github_repo = 'tests'
        self.tm.bitesized_tag = 'lowfruit'
        self.tm.documentation_tag = 'docs'
        self.tm.queries = [
            'https://api.github.com/repos/openhatch/tests/issues?state=open',
        ]
        spider.input_data = [self.tm.__dict__]

        url2filename = {
            'https://api.github.com/repos/openhatch/tests/issues?state=open':
                os.path.join(HERE, 'sample-data', 'github', 'issue-list'),
        }
        ar = autoresponse.Autoresponder(url2filename=url2filename,
                                        url2errors={})

        bugs = ar.respond_recursively(spider.start_requests())
        assert len(bugs) == 1

        bug = bugs[0]
        self.assertEqual(bug['canonical_bug_link'],
            'https://api.github.com/repos/openhatch/tests/issues/42')
        self.assertEqual(bug['canonical_bug_link'],
            'https://api.github.com/repos/openhatch/tests/issues/42')
        self.assertEqual(bug['title'], 'yo dawg')
        self.assertEqual(bug['description'], 'this issue be all up in ya biz-nass.')
        self.assertEqual(bug['status'], 'open')
        self.assertEqual(bug['people_involved'], 2)
        self.assertEqual(bug['date_reported'],
            printable_datetime(datetime.datetime(2012, 3, 12, 19, 24, 42)))
        self.assertEqual(bug['last_touched'],
            printable_datetime(datetime.datetime(2012, 3, 12, 21, 39, 42)))
        self.assertEqual(bug['submitter_username'], 'openhatch')
        self.assertEqual(bug['submitter_realname'], '')
        self.assertEqual(bug['canonical_bug_link'],
            'https://api.github.com/repos/openhatch/tests/issues/42')
        self.assertEqual(bug['good_for_newcomers'], True)
        self.assertEqual(bug['concerns_just_documentation'], False)
        self.assertEqual(bug['looks_closed'], False)

    def test_top_to_bottom_closed(self):
        spider = bugimporters.main.BugImportSpider()
        self.tm.bugimporter = 'github.GitHubBugImporter'
        self.tm.tracker_name = 'openhatch tests'
        self.tm.github_name = 'openhatch'
        self.tm.github_repo = 'tests'
        self.tm.bitesized_tag = 'lowfruit'
        self.tm.documentation_tag = 'docs'
        self.tm.queries = [
            'https://api.github.com/repos/openhatch/tests/issues?state=closed',
        ]
        spider.input_data = [self.tm.__dict__]

        url2filename = {
            'https://api.github.com/repos/openhatch/tests/issues?state=closed':
                os.path.join(HERE, 'sample-data', 'github', 'issue-list-closed'),
        }
        ar = autoresponse.Autoresponder(url2filename=url2filename,
                                        url2errors={})

        bugs = ar.respond_recursively(spider.start_requests())
        assert len(bugs) == 1

        bug = bugs[0]
        self.assertEqual(bug['canonical_bug_link'],
            'https://api.github.com/repos/openhatch/tests/issues/42')
        self.assertEqual(bug['canonical_bug_link'],
            'https://api.github.com/repos/openhatch/tests/issues/42')
        self.assertEqual(bug['title'], 'yo dawg')
        self.assertEqual(bug['description'], 'this issue be all up in ya biz-nass.')
        self.assertEqual(bug['status'], 'closed')
        self.assertEqual(bug['people_involved'], 2)
        self.assertEqual(bug['date_reported'],
            printable_datetime(datetime.datetime(2012, 3, 12, 19, 24, 42)))
        self.assertEqual(bug['last_touched'],
            printable_datetime(datetime.datetime(2012, 3, 16, 21, 39, 42)))
        self.assertEqual(bug['submitter_username'], 'openhatch')
        self.assertEqual(bug['submitter_realname'], '')
        self.assertEqual(bug['canonical_bug_link'],
            'https://api.github.com/repos/openhatch/tests/issues/42')
        self.assertEqual(bug['good_for_newcomers'], True)
        self.assertEqual(bug['concerns_just_documentation'], False)
        self.assertEqual(bug['looks_closed'], True)

    def test_process_bugs(self):
        url2filename = {
            'https://api.github.com/repos/openhatch/tests/issues/42':
                os.path.join(HERE, 'sample-data', 'github', 'issue-show'),
        }
        ar = autoresponse.Autoresponder(url2filename=url2filename,
                                        url2errors={})

        requests = self.im.process_bugs((
            ('https://api.github.com/repos/openhatch/tests/issues/42', None),
        ))
        bugs = ar.respond_recursively(requests)
        self.assertEqual(len(bugs), 1)

        bug = bugs[0]
        self.assertEqual(bug['canonical_bug_link'],
            'https://api.github.com/repos/openhatch/tests/issues/42')
        self.assertEqual(bug['canonical_bug_link'],
            'https://api.github.com/repos/openhatch/tests/issues/42')
        self.assertEqual(bug['title'], 'yo dawg')
        self.assertEqual(bug['description'], 'this issue be all up in ya biz-nass.')
        self.assertEqual(bug['status'], 'open')
        self.assertEqual(bug['people_involved'], 2)
        self.assertEqual(bug['date_reported'],
            printable_datetime(datetime.datetime(2012, 3, 12, 19, 24, 42)))
        self.assertEqual(bug['last_touched'],
            printable_datetime(datetime.datetime(2012, 3, 16, 21, 39, 42)))
        self.assertEqual(bug['submitter_username'], 'openhatch')
        self.assertEqual(bug['submitter_realname'], '')
        self.assertEqual(bug['canonical_bug_link'],
            'https://api.github.com/repos/openhatch/tests/issues/42')
        self.assertEqual(bug['good_for_newcomers'], True)
        self.assertEqual(bug['concerns_just_documentation'], False)
        self.assertEqual(bug['looks_closed'], False)