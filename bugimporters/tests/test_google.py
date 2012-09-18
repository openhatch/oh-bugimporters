import datetime
import os
import mock

from bugimporters.tests import Bug, ObjectFromDict
from bugimporters.google import GoogleBugParser
import bugimporters.trac
import bugimporters.main
import autoresponse
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

class MockGoogleTrackerModel(mock.Mock):
    tracker_name='SymPy'
    google_name='sympy'
    bitesized_type='label'
    bitesized_text='EasyToFix'
    documentation_type='label'
    documentation_text='Documentation'

class TestGoogleBugImport(object):
    @staticmethod
    def assertEqual(x, y):
        assert x == y

    def test_top_to_bottom(self):
        spider = bugimporters.main.BugImportSpider()
        spider.input_data = [dict(
                    tracker_name='SymPy',
                    google_name='sympy',
                    bitesized_type='label',
                    bitesized_text='EasyToFix',
                    documentation_type='label',
                    documentation_text='Documentation',
                    bugimporter = 'google.GoogleBugImporter',
                    queries=[
                    'https://code.google.com/feeds/issues/p/sympy/issues/full?can=open&max-results=10000' +
                    '&label=EasyToFix']
                    )]
        url2filename = {
            'https://code.google.com/feeds/issues/p/sympy/issues/full?can=open&max-results=10000&label=EasyToFix':
                os.path.join(HERE, 'sample-data', 'google',
                             'label-easytofix.atom'),
            }
        ar = autoresponse.Autoresponder(url2filename=url2filename,
                                        url2errors={})
        items = ar.respond_recursively(spider.start_requests())
        assert len(items) == 74

    def test_create_google_data_dict_with_everything(self):
        atom_dict = {
                'id': {'text': 'http://code.google.com/feeds/issues/p/sympy/issues/full/1215'},
                'published': {'text': '2008-11-24T11:15:58.000Z'},
                'updated': {'text': '2009-12-06T23:01:11.000Z'},
                'title': {'text': 'fix html documentation'},
                'content': {'text': """http://docs.sympy.org/modindex.html

I don't see for example the solvers module"""},
                'author': {'name': {'text': 'fabian.seoane'}},
                'cc': [
                    {'username': {'text': 'asmeurer'}}
                    ],
                'owner': {'username': {'text': 'Vinzent.Steinberg'}},
                'label': [
                    {'text': 'Type-Defect'},
                    {'text': 'Priority-Critical'},
                    {'text': 'Documentation'},
                    {'text': 'Milestone-Release0.6.6'}
                    ],
                'state': {'text': 'closed'},
                'status': {'text': 'Fixed'}
                }
        bug_atom = ObjectFromDict(atom_dict, recursive=True)
        gbp = GoogleBugParser(
                bug_url='http://code.google.com/p/sympy/issues/detail?id=1215')
        gbp.bug_atom = bug_atom

        got = gbp.get_parsed_data_dict(MockGoogleTrackerModel)
        wanted = {'title': 'fix html documentation',
                  'description': """http://docs.sympy.org/modindex.html

I don't see for example the solvers module""",
                  'status': 'Fixed',
                  'importance': 'Critical',
                  'people_involved': 3,
                  'date_reported': (
                datetime.datetime(2008, 11, 24, 11, 15, 58).isoformat()),
                  'last_touched': (
                datetime.datetime(2009, 12, 06, 23, 01, 11).isoformat()),
                  'looks_closed': True,
                  'submitter_username': 'fabian.seoane',
                  'submitter_realname': '',
                  'canonical_bug_link': 'http://code.google.com/p/sympy/issues/detail?id=1215',
                  'good_for_newcomers': False,
                  'concerns_just_documentation': True,
                  '_project_name': 'SymPy',
                  }
        self.assertEqual(wanted, got)

    def test_create_google_data_dict_author_in_list(self):
        atom_dict = {
                'id': {'text': 'http://code.google.com/feeds/issues/p/sympy/issues/full/1215'},
                'published': {'text': '2008-11-24T11:15:58.000Z'},
                'updated': {'text': '2009-12-06T23:01:11.000Z'},
                'title': {'text': 'fix html documentation'},
                'content': {'text': """http://docs.sympy.org/modindex.html

I don't see for example the solvers module"""},
                'author': [{'name': {'text': 'fabian.seoane'}}],
                'cc': [
                    {'username': {'text': 'asmeurer'}}
                    ],
                'owner': {'username': {'text': 'Vinzent.Steinberg'}},
                'label': [
                    {'text': 'Type-Defect'},
                    {'text': 'Priority-Critical'},
                    {'text': 'Documentation'},
                    {'text': 'Milestone-Release0.6.6'}
                    ],
                'state': {'text': 'closed'},
                'status': {'text': 'Fixed'}
                }
        bug_atom = ObjectFromDict(atom_dict, recursive=True)
        gbp = GoogleBugParser(
                bug_url='http://code.google.com/p/sympy/issues/detail?id=1215')
        gbp.bug_atom = bug_atom

        got = gbp.get_parsed_data_dict(MockGoogleTrackerModel)
        wanted = {'title': 'fix html documentation',
                  'description': """http://docs.sympy.org/modindex.html

I don't see for example the solvers module""",
                  'status': 'Fixed',
                  'importance': 'Critical',
                  'people_involved': 3,
                  'date_reported': (
                datetime.datetime(2008, 11, 24, 11, 15, 58).isoformat()),
                  'last_touched': (
                datetime.datetime(2009, 12, 06, 23, 01, 11).isoformat()),
                  'looks_closed': True,
                  'submitter_username': 'fabian.seoane',
                  'submitter_realname': '',
                  'canonical_bug_link': 'http://code.google.com/p/sympy/issues/detail?id=1215',
                  'good_for_newcomers': False,
                  'concerns_just_documentation': True,
                  '_project_name': 'SymPy',
                  }
        self.assertEqual(wanted, got)

    def test_create_google_data_dict_owner_in_list(self):
        atom_dict = {
                'id': {'text': 'http://code.google.com/feeds/issues/p/sympy/issues/full/1215'},
                'published': {'text': '2008-11-24T11:15:58.000Z'},
                'updated': {'text': '2009-12-06T23:01:11.000Z'},
                'title': {'text': 'fix html documentation'},
                'content': {'text': """http://docs.sympy.org/modindex.html

I don't see for example the solvers module"""},
                'author': {'name': {'text': 'fabian.seoane'}},
                'cc': [
                    {'username': {'text': 'asmeurer'}}
                    ],
                'owner': [{'username': {'text': 'Vinzent.Steinberg'}}],
                'label': [
                    {'text': 'Type-Defect'},
                    {'text': 'Priority-Critical'},
                    {'text': 'Documentation'},
                    {'text': 'Milestone-Release0.6.6'}
                    ],
                'state': {'text': 'closed'},
                'status': {'text': 'Fixed'}
                }
        bug_atom = ObjectFromDict(atom_dict, recursive=True)
        gbp = GoogleBugParser(
                bug_url='http://code.google.com/p/sympy/issues/detail?id=1215')
        gbp.bug_atom = bug_atom

        got = gbp.get_parsed_data_dict(MockGoogleTrackerModel)
        wanted = {'title': 'fix html documentation',
                  'description': """http://docs.sympy.org/modindex.html

I don't see for example the solvers module""",
                  'status': 'Fixed',
                  'importance': 'Critical',
                  'people_involved': 3,
                  'date_reported': (
                datetime.datetime(2008, 11, 24, 11, 15, 58).isoformat()),
                  'last_touched': (
                datetime.datetime(2009, 12, 06, 23, 01, 11).isoformat()),
                  'looks_closed': True,
                  'submitter_username': 'fabian.seoane',
                  'submitter_realname': '',
                  'canonical_bug_link': 'http://code.google.com/p/sympy/issues/detail?id=1215',
                  'good_for_newcomers': False,
                  'concerns_just_documentation': True,
                  '_project_name': 'SymPy',
                  }
        self.assertEqual(wanted, got)

    def test_create_google_data_dict_without_status(self):
        atom_dict = {
                'id': {'text': 'http://code.google.com/feeds/issues/p/sympy/issues/full/1215'},
                'published': {'text': '2008-11-24T11:15:58.000Z'},
                'updated': {'text': '2009-12-06T23:01:11.000Z'},
                'title': {'text': 'fix html documentation'},
                'content': {'text': """http://docs.sympy.org/modindex.html

I don't see for example the solvers module"""},
                'author': {'name': {'text': 'fabian.seoane'}},
                'cc': [
                    {'username': {'text': 'asmeurer'}}
                    ],
                'owner': {'username': {'text': 'Vinzent.Steinberg'}},
                'label': [
                    {'text': 'Type-Defect'},
                    {'text': 'Priority-Critical'},
                    {'text': 'Documentation'},
                    {'text': 'Milestone-Release0.6.6'}
                    ],
                'state': {'text': 'closed'},
                'status': None
                }
        bug_atom = ObjectFromDict(atom_dict, recursive=True)
        gbp = GoogleBugParser(
                bug_url='http://code.google.com/p/sympy/issues/detail?id=1215')
        gbp.bug_atom = bug_atom

        got = gbp.get_parsed_data_dict(MockGoogleTrackerModel)
        wanted = {'title': 'fix html documentation',
                  'description': """http://docs.sympy.org/modindex.html

I don't see for example the solvers module""",
                  'status': '',
                  'importance': 'Critical',
                  'people_involved': 3,
                  'date_reported': (
                datetime.datetime(2008, 11, 24, 11, 15, 58).isoformat()),
                  'last_touched': (
                datetime.datetime(2009, 12, 06, 23, 01, 11).isoformat()),
                  'looks_closed': True,
                  'submitter_username': 'fabian.seoane',
                  'submitter_realname': '',
                  'canonical_bug_link': 'http://code.google.com/p/sympy/issues/detail?id=1215',
                  'good_for_newcomers': False,
                  'concerns_just_documentation': True,
                  '_project_name': 'SymPy',
                  }
        self.assertEqual(wanted, got)

