import datetime
import os

import bugimporters.roundup
from bugimporters.tests import ObjectFromDict
import bugimporters.tests
import bugimporters.main
import autoresponse

HERE = os.path.dirname(os.path.abspath(__file__))

class TestRoundupBugImporter(object):
    @staticmethod
    def assertEqual(x, y):
        assert x == y

    def setup_class(cls):
        # Set up the RoundupTrackerModel that will be used here.
        cls.tm = ObjectFromDict(dict(
                tracker_name='Mercurial',
                base_url='http://mercurial.selenic.com/bts/',
                closed_status='resolved',
                bitesized_field='Topics',
                bitesized_text='bitesized',
                documentation_field='Topics',
                documentation_text='documentation',
                as_appears_in_distribution='',
                bugimporter='roundup.RoundupBugImporter',
                queries = ['http://mercurial.selenic.com/bts/issue?@action=export_csv&@columns=id,activity,title,creator,status&@sort=-activity&@group=priority&@filter=status,assignedto&@pagesize=50&@startwith=0&status=-1,1,2,3,4,5,6,7,9,10'],
                ))
        cls.im = bugimporters.roundup.RoundupBugImporter(
            cls.tm,
            bugimporters.tests.ReactorManager(),
            data_transits=None)

    def test_bug_import_works_with_comma_separated_closed_status(self):
        # First, change the environment -- pretend the user on the web interface
        # said that there are two status values that mean 'closed' for
        # the Mercurial project.
        self.tm.closed_status = 'wontfix,resolved'
        # Now, run an existing test -- this verifies that looks_closed
        # is set to True.
        item = self.test_new_mercurial_bug_import()
        assert item['looks_closed'] == True

    def test_top_to_bottom(self):
        spider = bugimporters.main.BugImportSpider()
        spider.input_data = [self.tm.__dict__]
        url2filename = {'http://mercurial.selenic.com/bts/issue?@action=export_csv&@columns=id,activity,title,creator,status&@sort=-activity&@group=priority&@filter=status,assignedto&@pagesize=50&@startwith=0&status=-1,1,2,3,4,5,6,7,9,10':
                            os.path.join(HERE, 'sample-data', 'fake-mercurial-csv.csv'),
                        'http://mercurial.selenic.com/bts/issue1550':
                            os.path.join(HERE, 'sample-data', 'closed-mercurial-bug.html'),
                        }
        ar = autoresponse.Autoresponder(url2filename=url2filename,
                                        url2errors={})
        items = ar.respond_recursively(spider.start_requests())
        assert len(items) == 1
        item = items[0]
        assert item['canonical_bug_link'] == (
            'http://mercurial.selenic.com/bts/issue1550')

    def test_new_mercurial_bug_import(self):
        # Check the number of Bugs present.
        rbp = bugimporters.roundup.RoundupBugParser(
                bug_url='http://mercurial.selenic.com/bts/issue1550')
        # Parse HTML document as if we got it from the web
        bug = self.im.handle_bug_html(open(os.path.join(
                    HERE, 'sample-data',
                    'closed-mercurial-bug.html')).read(), rbp )

        self.assertEqual(bug['_project_name'], 'Mercurial')
        self.assertEqual(bug['title'], "help('modules') broken by several 3rd party libraries (svn patch attached)")
        self.assertEqual(bug['description'], """Instead of listing installed modules, help('modules') prints a "please
wait" message, then a traceback noting that a module raised an exception
during import, then nothing else.
This happens in 2.5 and 2.6a0, but not in 2.4, which apparently doesn't
__import__() EVERY module.
Tested only on Gentoo Linux 2.6.19, but same behavior is probable on
other platforms because pydoc and pkgutil are written in cross-platform
Python.

Prominent 3rd party libraries that break help('modules') include Django,
Pyglet, wxPython, SymPy, and Pypy. Arguably, the bug is in those
libraries, but they have good reasons for their behavior. Also, the Unix
philosophy of forgiving input is a good one. Also, __import__()ing every
module takes a significant run-time hit, especially if libraries compute
eg. configuration.

The patch utilizes a pre-existing hook in pkgutil to simply quietly add
the module to the output. (Long live lambda.)""")
        self.assertEqual(bug['status'], 'resolved')
        self.assertEqual(bug['importance'], 'normal')
        self.assertEqual(bug['people_involved'], 2)
        self.assertEqual(bug['date_reported'], datetime.datetime(2007, 12, 3, 16, 34).isoformat())
        self.assertEqual(bug['last_touched'], datetime.datetime(2008, 1, 13, 11, 32).isoformat())
        self.assertEqual(bug['submitter_username'], 'benjhayden')
        self.assertEqual(bug['submitter_realname'], 'Ben Hayden')
        self.assertEqual(bug['canonical_bug_link'], 'http://mercurial.selenic.com/bts/issue1550')
        assert bug['good_for_newcomers']
        assert bug['looks_closed']
        return bug

    def test_reimport_same_bug_works(self):
        bug1 = self.test_new_mercurial_bug_import()
        bug2 = self.test_new_mercurial_bug_import()
        assert bug2['last_polled'] > bug1['last_polled']

class TestRoundupBugsFromPythonProject(object):
    @staticmethod
    def assertEqual(x, y):
        assert x == y

    def setup_class(cls):
        # Set up the RoundupTrackerModel that will be used here.
        cls.tm = ObjectFromDict(dict(
                tracker_name='Python',
                base_url='http://bugs.python.org/',
                closed_status='resolved',
                bitesized_field='Keywords',
                bitesized_text='easy',
                documentation_field='Components',
                documentation_text='Documentation',
                as_appears_in_distribution='',
                ))
        cls.im = bugimporters.roundup.RoundupBugImporter(
            cls.tm,
            bugimporters.tests.ReactorManager(),
            data_transits=None)

    def test_bug_import(self):
        # Check the number of Bugs present.
        rbp = bugimporters.roundup.RoundupBugParser(
                bug_url='http://bugs.python.org/issue8264')
        # Parse HTML document as if we got it from the web
        bug = self.im.handle_bug_html(open(os.path.join(
                        HERE, 'sample-data',
                        'python-roundup-8264.html')).read(), rbp)

        self.assertEqual(bug['_project_name'], 'Python')
        self.assertEqual(bug['title'], "hasattr doensn't show private (double underscore) attributes exist")
