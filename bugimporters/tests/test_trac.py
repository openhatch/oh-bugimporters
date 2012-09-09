import datetime
import os
import autoresponse

from bugimporters.tests import (ReactorManager, TrackerModel,
        HaskellTrackerModel)
from bugimporters.base import printable_datetime
from bugimporters.trac import TracBugImporter, TracBugParser, TracSpider
from mock import Mock


HERE = os.path.dirname(os.path.abspath(__file__))

# Create a global variable that can be referenced both from inside tests
# and from module level functions functions.

bug_data_transit = {
    'get_fresh_urls': None,
    'update': None,
    'delete_by_url': None,
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

    def test_top_to_bottom(self):
        spider = TracSpider()
        self.tm.bugimporter = 'trac.TracBugImporter'
        self.tm.tracker_name = 'Twisted'
        self.tm.bitesized_type = ''
        self.tm.documentation_type = ''
        self.tm.base_url = 'http://twistedmatrix.com/trac/'
        self.tm.queries = ['http://twistedmatrix.com/trac/query?id=5858&format=csv']
        spider.input_data = [self.tm.__dict__]
        url2filename = {'http://twistedmatrix.com/trac/query?id=5858&format=csv':
                            os.path.join(HERE, 'sample-data', 'twisted-trac-query-for-id=5858.csv'),
                        'http://twistedmatrix.com/trac/ticket/5858?format=csv':
                            os.path.join(HERE, 'sample-data', 'twisted-trac-5858.csv'),
                        'http://twistedmatrix.com/trac/ticket/5858':
                            os.path.join(HERE, 'sample-data', 'twisted-trac-5858.html'),
                        }
        ar = autoresponse.Autoresponder(url2filename=url2filename,
                                        url2errors={})
        items = ar.respond_recursively(spider.start_requests())
        assert len(items) == 1
        item = items[0]
        assert item['canonical_bug_link'] == (
            'http://twistedmatrix.com/trac/ticket/5858')

    def test_handle_query_csv(self):
        self.im.bug_ids = []
        cached_csv_filename = os.path.join(HERE, 'sample-data',
                'twisted-trac-query-easy-bugs-on-2011-04-13.csv')
        items = list(self.im.handle_query_csv(unicode(
                open(cached_csv_filename).read(), 'utf-8')))

        assert len(items) == 18

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

    def test_handle_bug_html_for_new_bug(self):
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
        item = self.im.handle_bug_html(unicode(
                open(cached_html_filename).read(), 'utf-8'), tbp)

        # Check there is now one Bug.
        assert item['title'] == 'Deprecate twisted.persisted.journal'
        assert item['submitter_username'] == 'thijs'
        assert item['_tracker_name'] == self.tm.tracker_name
        return item

    def test_handle_bug_html_for_existing_bug(self):
        item_first_time = self.test_handle_bug_html_for_new_bug()
        item_second_time = self.test_handle_bug_html_for_new_bug()
        assert (item_second_time['last_polled'] >
                item_first_time['last_polled'])

    def test_bug_that_404s_is_deleted(self, monkeypatch):
        bug_url = 'http://twistedmatrix.com/trac/ticket/1234'
        ar = autoresponse.Autoresponder(url2filename={},
                          url2errors={
                bug_url + '?format=csv': 404,
                })

        all_bugs = [(bug_url, None)]

        request_iterable = self.im.process_bugs(all_bugs)
        items = ar.respond_recursively(request_iterable)

        assert len(items) == 1
        assert items[0]['_deleted']

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

class TestTracBugParser(object):
    @staticmethod
    def assertEqual(x, y):
        assert x == y

    def setup_class(cls):
        cls.tm = TrackerModel()
        cls.im = TracBugImporter(cls.tm, ReactorManager(),
                data_transits=importer_data_transits)

        # Set up the Twisted TrackerModels that will be used here.
        cls.tm = TrackerModel(
                tracker_name='Twisted',
                base_url='http://twistedmatrix.com/trac/',
                bug_project_name_format='{tracker_name}',
                bitesized_type='keywords',
                bitesized_text='easy',
                documentation_type='keywords',
                documentation_text='documentation')
        cls.tm2 = TrackerModel(
                tracker_name='Trac',
                base_url='http://trac.edgewall.org/',
                bug_project_name_format='{tracker_name}',
                bitesized_type='keywords',
                bitesized_text='bitesized',
                documentation_type='')
        cls.tm3 = TrackerModel(
                tracker_name='Tracpriority',
                base_url='http://trac.edgewall.org/priority',
                bug_project_name_format='{tracker_name}',
                bitesized_type='priority',
                bitesized_text='trivial',
                documentation_type='')
        cls.tm4 = TrackerModel(
                tracker_name='Tango',
                base_url='http://dsource.org/projects/tango/',
                bug_project_name_format='{tracker_name}',
                documentation_type='')

    def test_create_bug_object_data_dict_more_recent(self):
        tbp = TracBugParser('http://twistedmatrix.com/trac/ticket/4298')
        tbp.bug_csv = {
            'branch': '',
            'branch_author': '',
            'cc': 'thijs_ exarkun',
            'component': 'core',
            'description': "This package hasn't been touched in 4 years which either means it's stable or not being used at all. Let's deprecate it (also see #4111).",
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
            'type': 'task'}
        cached_html_filename = os.path.join(HERE, 'sample-data', 'twisted-trac-4298-on-2010-04-02.html')
        tbp.set_bug_html_data(unicode(
            open(cached_html_filename).read(), 'utf-8'))

        self.assertEqual(tbp.component, 'core')

        got = tbp.get_parsed_data_dict(self.tm)
        del got['last_polled']
        wanted = {'title': 'Deprecate twisted.persisted.journal',
                  'description': "This package hasn't been touched in 4 years which either means it's stable or not being used at all. Let's deprecate it (also see #4111).",
                  'status': 'new',
                  'importance': 'normal',
                  'people_involved': 4,
                  # FIXME: Need time zone
                  'date_reported': printable_datetime(
                datetime.datetime(2010, 2, 23, 0, 46, 30)),
                  'last_touched': printable_datetime(
                datetime.datetime(2010, 3, 12, 18, 43, 5)),
                  'looks_closed': False,
                  'submitter_username': 'thijs',
                  'submitter_realname': '',
                  'canonical_bug_link': 'http://twistedmatrix.com/trac/ticket/4298',
                  'good_for_newcomers': True,
                  'looks_closed': False,
                  'concerns_just_documentation': False,
                  '_project_name': 'Twisted',
                  'as_appears_in_distribution': '',
                  }
        self.assertEqual(wanted, got)

    def test_create_bug_object_data_dict(self):
        tbp = TracBugParser('http://twistedmatrix.com/trac/ticket/4298')
        tbp.bug_csv = {
            'branch': '',
            'branch_author': '',
            'cc': 'thijs_ exarkun',
            'component': 'core',
            'description': "This package hasn't been touched in 4 years which either means it's stable or not being used at all. Let's deprecate it (also see #4111).",
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
            'type': 'task'}
        cached_html_filename = os.path.join(HERE, 'sample-data', 'twisted-trac-4298.html')
        tbp.set_bug_html_data(unicode(
            open(cached_html_filename).read(), 'utf-8'))

        got = tbp.get_parsed_data_dict(self.tm)
        del got['last_polled']
        wanted = {'title': 'Deprecate twisted.persisted.journal',
                  'description': "This package hasn't been touched in 4 years which either means it's stable or not being used at all. Let's deprecate it (also see #4111).",
                  'status': 'new',
                  'importance': 'normal',
                  'people_involved': 5,
                  # FIXME: Need time zone
                  'date_reported': printable_datetime(
                datetime.datetime(2010, 2, 22, 19, 46, 30)),
                  'last_touched': printable_datetime(
                datetime.datetime(2010, 2, 24, 0, 8, 47)),
                  'looks_closed': False,
                  'submitter_username': 'thijs',
                  'submitter_realname': '',
                  'canonical_bug_link': 'http://twistedmatrix.com/trac/ticket/4298',
                  'good_for_newcomers': True,
                  'looks_closed': False,
                  '_project_name': 'Twisted',
                  'concerns_just_documentation': False,
                  'as_appears_in_distribution': '',
                  }
        self.assertEqual(wanted, got)

    def test_create_bug_object_data_dict_priority_bitesized(self):
        self.maxDiff = None
        tbp = TracBugParser('http://twistedmatrix.com/trac/ticket/4298')
        tbp.bug_csv = {
            'branch': '',
            'branch_author': '',
            'cc': 'thijs_ exarkun',
            'component': 'core',
            'description': "This package hasn't been touched in 4 years which either means it's stable or not being used at all. Let's deprecate it (also see #4111).",
            'id': '4298',
            'keywords': 'easy',
            'launchpad_bug': '',
            'milestone': '',
            'owner': 'djfroofy',
            'priority': 'trivial',
            'reporter': 'thijs',
            'resolution': '',
            'status': 'new',
            'summary': 'Deprecate twisted.persisted.journal',
            'type': 'task'}
        cached_html_filename = os.path.join(HERE, 'sample-data', 'twisted-trac-4298.html')
        tbp.set_bug_html_data(unicode(
            open(cached_html_filename).read(), 'utf-8'))

        got = tbp.get_parsed_data_dict(self.tm3)
        del got['last_polled']
        wanted = {'title': 'Deprecate twisted.persisted.journal',
                  'description': u"This package hasn't been touched in 4 years which either means it's stable or not being used at all. Let's deprecate it (also see #4111).",
                  'status': 'new',
                  'importance': 'trivial',
                  'people_involved': 5,
                  # FIXME: Need time zone
                  'date_reported': printable_datetime(
                datetime.datetime(2010, 2, 22, 19, 46, 30)),
                  'last_touched': printable_datetime(
                datetime.datetime(2010, 2, 24, 0, 8, 47)),
                  'looks_closed': False,
                  'submitter_username': 'thijs',
                  'submitter_realname': '',
                  'canonical_bug_link': 'http://twistedmatrix.com/trac/ticket/4298',
                  'good_for_newcomers': True,
                  'looks_closed': False,
                  '_project_name': 'Tracpriority',
                  'concerns_just_documentation': False,
                  'as_appears_in_distribution': '',
                  }
        self.assertEqual(wanted, got)

    def test_create_bug_that_lacks_modified_date(self):
        tbp = TracBugParser('http://twistedmatrix.com/trac/ticket/4298')
        tbp.bug_csv = {
            'branch': '',
            'branch_author': '',
            'cc': 'thijs_ exarkun',
            'component': 'core',
            'description': "This package hasn't been touched in 4 years which either means it's stable or not being used at all. Let's deprecate it (also see #4111).",
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
            'type': 'task'}
        cached_html_filename = os.path.join(HERE, 'sample-data', 'twisted-trac-4298-without-modified.html')
        tbp.set_bug_html_data(unicode(
            open(cached_html_filename).read(), 'utf-8'))

        got = tbp.get_parsed_data_dict(self.tm)
        del got['last_polled']
        wanted = {'title': 'Deprecate twisted.persisted.journal',
                  'description': "This package hasn't been touched in 4 years which either means it's stable or not being used at all. Let's deprecate it (also see #4111).",
                  'status': 'new',
                  'importance': 'normal',
                  'people_involved': 5,
                  # FIXME: Need time zone
                  'date_reported': printable_datetime(
                datetime.datetime(2010, 2, 22, 19, 46, 30)),
                  'last_touched': printable_datetime(
                datetime.datetime(2010, 2, 22, 19, 46, 30)),
                  'looks_closed': False,
                  'submitter_username': 'thijs',
                  'submitter_realname': '',
                  'canonical_bug_link': 'http://twistedmatrix.com/trac/ticket/4298',
                  'good_for_newcomers': True,
                  'looks_closed': False,
                  'concerns_just_documentation': False,
                  'as_appears_in_distribution': '',
                  '_project_name': 'Twisted',
                  }
        self.assertEqual(wanted, got)

    def test_create_bug_that_lacks_modified_date_and_uses_owned_by_instead_of_assigned_to(self):
        tbp = TracBugParser('http://twistedmatrix.com/trac/ticket/4298')
        tbp.bug_csv = {
            'branch': '',
            'branch_author': '',
            'cc': 'thijs_ exarkun',
            'component': 'core',
            'description': "This package hasn't been touched in 4 years which either means it's stable or not being used at all. Let's deprecate it (also see #4111).",
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
            'type': 'task'}
        cached_html_filename = os.path.join(HERE, 'sample-data', 'twisted-trac-4298-without-modified-using-owned-instead-of-assigned.html')
        tbp.set_bug_html_data(unicode(
            open(cached_html_filename).read(), 'utf-8'))

        got = tbp.get_parsed_data_dict(self.tm)
        del got['last_polled']
        wanted = {'title': 'Deprecate twisted.persisted.journal',
                  'description': "This package hasn't been touched in 4 years which either means it's stable or not being used at all. Let's deprecate it (also see #4111).",
                  'status': 'new',
                  'importance': 'normal',
                  'people_involved': 5,
                  # FIXME: Need time zone
                  'date_reported': printable_datetime(
                datetime.datetime(2010, 2, 22, 19, 46, 30)),
                  'last_touched': printable_datetime(
                datetime.datetime(2010, 2, 22, 19, 46, 30)),
                  'looks_closed': False,
                  'submitter_username': 'thijs',
                  'submitter_realname': '',
                  'canonical_bug_link': 'http://twistedmatrix.com/trac/ticket/4298',
                  'good_for_newcomers': True,
                  'looks_closed': False,
                  'concerns_just_documentation': False,
                  '_project_name': 'Twisted',
                  'as_appears_in_distribution': '',
                  }
        self.assertEqual(wanted, got)

    def test_create_bug_that_has_new_date_format(self):
        tbp = TracBugParser('http://trac.edgewall.org/ticket/3275')
        tbp.bug_csv = {
                  'description': u"Hi\r\n\r\nWhen embedding sourcecode in wiki pages using the {{{-Makro, I would sometimes like to have line numbers displayed. This would make it possible to reference some lines in a text, like: \r\n\r\n''We got some c-sourcecode here, in line 1, a buffer is allocated, in line 35, some data is copied to the buffer without checking the size of the data...''\r\n\r\nThe svn browser shows line numbers, so I hope this will not be so difficult.",
                  'status': 'new',
                  'keywords': '',
                  'summary': 'Show line numbers when embedding source code in wiki pages',
                  'priority': '',
                  'reporter': 'erik@\xe2\x80\xa6',
                  'id': '3275'}
        cached_html_filename = os.path.join(HERE, 'sample-data', 'trac-3275.html')
        tbp.set_bug_html_data(unicode(
            open(cached_html_filename).read(), 'utf-8'))

        got = tbp.get_parsed_data_dict(self.tm2)
        del got['last_polled']
        wanted = {'status': 'new',
                  'as_appears_in_distribution': u'',
                  'description': u"Hi\r\n\r\nWhen embedding sourcecode in wiki pages using the {{{-Makro, I would sometimes like to have line numbers displayed. This would make it possible to reference some lines in a text, like: \r\n\r\n''We got some c-sourcecode here, in line 1, a buffer is allocated, in line 35, some data is copied to the buffer without checking the size of the data...''\r\n\r\nThe svn browser shows line numbers, so I hope this will not be so difficult.",
                  'importance': '',
                  'canonical_bug_link': 'http://trac.edgewall.org/ticket/3275',
                  'date_reported': printable_datetime(
                datetime.datetime(2006, 6, 16, 15, 1, 52)),
                  'submitter_realname': '',
                  'title': 'Show line numbers when embedding source code in wiki pages',
                  'people_involved': 3,
                  'last_touched': printable_datetime(
                datetime.datetime(2010, 11, 26, 13, 45, 45)),
                  'submitter_username': 'erik@\xe2\x80\xa6',
                  'looks_closed': False,
                  'good_for_newcomers': False,
                  'concerns_just_documentation': False,
                  '_project_name': 'Trac',
                  }
        self.assertEqual(wanted, got)

    def test_create_bug_that_has_another_date_format(self):
        tbp = TracBugParser('http://dsource.org/projects/tango/ticket/1939')
        tbp.bug_csv = {
            'cc': '',
            'component': 'Documentation',
            'description': "tango.core.Memory.GC.monitor() is documented incorrectly. It just duplicates previous function documentation. At least in Kai. Can't see current trunk Memory module for some reason.\\r\\n",
            'id': '1939',
            'keywords': 'GC.monitor',
            'milestone': 'Documentation',
            'owner': 'community',
            'priority': 'trivial',
            'reporter': '~Gh0sT~',
            'resolution': '',
            'status': 'new',
            'summary': 'tango.core.Memory.GC.monitor() is documented incorrectly',
            'type': 'defect',
            'version': '0.99.9 Kai',
            }

        cached_html_filename = os.path.join(HERE, 'sample-data', 'dsource-1939')
        tbp.set_bug_html_data(unicode(
            open(cached_html_filename).read(), 'utf-8'))

        got = tbp.get_parsed_data_dict(self.tm4)
        wanted_date = printable_datetime(
            datetime.datetime(2010, 6, 19, 8, 15, 37))
        self.assertEqual(wanted_date, got['date_reported'])
        self.assertEqual(wanted_date, got['last_touched'])
