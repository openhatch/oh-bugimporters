from datetime import datetime, timedelta
import os
import twisted

from bugimporters.tests import (Bug, ReactorManager, TrackerModel,
        FakeGetPage, HaskellTrackerModel)
from bugimporters.trac import TracBugImporter, TracBugParser
from mock import Mock


HERE = os.path.dirname(os.path.abspath(__file__))

# Create a global variable that can be referenced both from inside tests
# and from module level functions functions.
all_bugs = []


def delete_by_url(url):
    for index, bug in enumerate(all_bugs):
        if bug[0] == url:
            del all_bugs[index]
            break

bug_data_transit = {
    'get_fresh_urls': lambda *args: {},
    'update': lambda value: all_bugs.append(Bug(value)),
    'delete_by_url': delete_by_url,
}

trac_data_transit = {
    'get_bug_times': lambda url: (None, None),
    'get_timeline_url': Mock(),
    'update_timeline': Mock()
}

importer_data_transits = {'bug': bug_data_transit, 'trac': trac_data_transit}


class TestTracBugImporter(object):

    def setup_class(cls):
        cls.tm = TrackerModel()
        cls.im = TracBugImporter(cls.tm, ReactorManager(),
                data_transits=importer_data_transits)
        global all_bugs
        all_bugs = []

    def test_handle_query_csv(self):
        self.im.bug_ids = []
        cached_csv_filename = os.path.join(HERE, 'sample-data',
                'twisted-trac-query-easy-bugs-on-2011-04-13.csv')
        self.im.handle_query_csv(unicode(
                open(cached_csv_filename).read(), 'utf-8'))

        assert len(self.im.bug_ids) == 18

    def test_bug_parser(self):
        ### As an aside:
        # TracBugParser is amusing, as it pulls data from two different sources.
        # 1. Data pulled from the Trac API, which is stored for the parser's
        #    benefit in csv_data.
        # 2. Data that must be scraped from the Trac web app, since the API
        #    doesn't expose everything. This gets stored in html_data.

        # In this test, we provide versions of that data that we downloaded
        # in the past so that we can make this test run fast and reliably.
        # By providing the data here, we permit the test to run without
        # accessing the network.

        # Create a new TracBugParser that is aware of the URL it refers to
        tbp = TracBugParser(
                bug_url='http://twistedmatrix.com/trac/ticket/4298')

        # Add data to avoid the network hit
        # (This is a file you can get by calling 'wget' on the above ticket URL.)
        cached_html_filename = os.path.join(HERE, 'sample-data',
                'twisted-trac-4298-on-2010-04-02.html')
        tbp.set_bug_html_data(unicode(
            open(cached_html_filename).read(), 'utf-8'))

        # This CSV data comes from visiting
        # http://twistedmatrix.com/trac/ticket/4298 and clicking
        # "Comma-delimited text" at the bottom.
        tbp.set_bug_csv_data(open(os.path.join(HERE, 'sample-data',
                'twisted-trac-4298-csv-export')).read())

        # Provide a fake "tracker model", which is a little bit of data that
        # corresponds to information about the open source project in question
        # and how its bug tracker is configured.
        tm = TrackerModel()

        # Now, actually look at the data returned by the BugParser object
        # and verify its output through assertions.
        returned_data = tbp.get_parsed_data_dict(tm)
        assert returned_data['title'] == 'Deprecate twisted.persisted.journal'
        assert returned_data['good_for_newcomers']

    def test_handle_bug_html_for_new_bug(self, second_run=False):
        if second_run:
            assert len(all_bugs) == 1
            old_last_polled = all_bugs[0].last_polled
        else:
            assert len(all_bugs) == 0

        tbp = TracBugParser(
                bug_url='http://twistedmatrix.com/trac/ticket/4298')
        tbp.bug_csv = {
            'branch': '',
            'branch_author': '',
            'cc': 'thijs_ exarkun',
            'component': 'core',
            'description': "This package hasn't been touched in 4 years' \
                    'which either means it's stable or not being used at ' \
                    'all. Let's deprecate it (also see #4111).",
            'id': '4298',
            'keywords': 'easy',
            'launchpad_bug': '',
            'milestone': '',
            'owner': 'djfroofy',
            'priority': 'normal',
            'reporter': 'thijs',
            'resolution': '',
            'status': 'new',
            'summary': 'Deprecate twisted.persisted.journal',
            'type': 'task'
        }

        cached_html_filename = os.path.join(HERE, 'sample-data',
                'twisted-trac-4298-on-2010-04-02.html')
        self.im.handle_bug_html(unicode(
            open(cached_html_filename).read(), 'utf-8'), tbp)

        # Check there is now one Bug.

        bug = all_bugs[0]

        if second_run:
            assert len(all_bugs) == 2
            bug = all_bugs[1]
            assert bug.last_polled > old_last_polled
        else:
            assert len(all_bugs) == 1
            bug = all_bugs[0]

        assert bug.title == 'Deprecate twisted.persisted.journal'
        assert bug.submitter_username == 'thijs'
        assert bug.tracker == self.tm

    def test_handle_bug_html_for_existing_bug(self):
        global all_bugs
        all_bugs = []

        self.test_handle_bug_html_for_new_bug()
        self.test_handle_bug_html_for_new_bug(second_run=True)

    def test_bug_that_404s_is_deleted(self, monkeypatch):
        monkeypatch.setattr(twisted.web.client, 'getPage',
                FakeGetPage().get404)

        bug = {
            'project': Mock(),
            'canonical_bug_link': 'http://twistedmatrix.com/trac/ticket/1234',
            'date_reported': datetime.utcnow(),
            'last_touched': datetime.utcnow(),
            'last_polled': datetime.utcnow() - timedelta(days=2),
            'tracker': self.tm,
        }

        global all_bugs
        all_bugs = [[bug['canonical_bug_link'], bug]]

        self.im.process_bugs(all_bugs)
        assert len(all_bugs) == 0

    def test_bug_with_difficulty_easy_is_bitesize(self):
        tbp = TracBugParser(
                bug_url='http://hackage.haskell.org/trac/ghc/ticket/4268')

        cached_html_filename = os.path.join(HERE, 'sample-data',
                'ghc-trac-4268.html')
        tbp.set_bug_html_data(unicode(
            open(cached_html_filename).read(), 'utf-8'))

        cached_csv_filename = os.path.join(HERE, 'sample-data',
                'ghc-trac-4268.csv')
        tbp.set_bug_csv_data(open(cached_csv_filename).read())

        tm = HaskellTrackerModel()

        returned_data = tbp.get_parsed_data_dict(tm)
        assert returned_data['good_for_newcomers'], '''The bug is considered
                    good_for_newcomers because the value of the difficulty
                    field is: "Easy (less than 1 hour)"'''
