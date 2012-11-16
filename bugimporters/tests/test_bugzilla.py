import datetime
import os
import lxml
import mock

import bugimporters.bugzilla
import bugimporters.tests
import bugimporters.main
import autoresponse

HERE = os.path.dirname(os.path.abspath(__file__))
def sample_data_path(f):
    return os.path.join(HERE, 'sample-data', 'bugzilla', f)

class TestCustomBugParser(object):
    @staticmethod
    def assertEqual(x, y):
        assert x == y

    ### First, test that if we create the bug importer correctly, the
    ### right thing would happen.
    def test_bugzilla_bug_importer_uses_bugzilla_parser_by_default(self):
        bbi = bugimporters.bugzilla.BugzillaBugImporter(
            tracker_model=None, reactor_manager=None,
            bug_parser=None)
        self.assertEqual(bbi.bug_parser,
                         bugimporters.bugzilla.BugzillaBugParser)

    def test_bugzilla_bug_importer_accepts_bug_parser(self):
        bbi = bugimporters.bugzilla.BugzillaBugImporter(
            tracker_model=None, reactor_manager=None,
            bug_parser=bugimporters.bugzilla.KDEBugzilla)
        self.assertEqual(bbi.bug_parser, bugimporters.bugzilla.KDEBugzilla)

    def test_kdebugparser_uses_tracker_specific_method(self):
        with mock.patch('bugimporters.bugzilla.KDEBugzilla.extract_tracker_specific_data') as mock_specific:
            with open(sample_data_path('kde-117760-2010-04-09.xml')) as f:
                bugzilla_data = lxml.etree.XML(f.read())

            bug_data = bugzilla_data.xpath('bug')[0]

            kdebugzilla = bugimporters.bugzilla.KDEBugzilla(bug_data)
            kdebugzilla.get_parsed_data_dict(base_url='http://bugs.kde.org/',
                                             bitesized_type=None,
                                             bitesized_text='',
                                             documentation_type=None,
                                             documentation_text='')
            assert mock_specific.called
    ### Now, test that the bug import spider will create an importer
    ### configured to use the right class.
    def test_customs_twist_creates_importers_correctly(self):
        tm = dict(
            tracker_name='KDE Bugzilla',
            base_url='http://bugs.kde.org/',
            bug_project_name_format='{tracker_name}',
            bitesized_type='key',
            bitesized_text='bitesized',
            documentation_type='key',
            custom_parser='bugzilla.KDEBugzilla',
            bugimporter='bugzilla',
            )

        spider = bugimporters.main.BugImportSpider()
        spider.input_data = [tm]
        bug_importer_and_objs = list(spider.get_bugimporters())
        assert len(bug_importer_and_objs) == 1
        obj, bug_importer = bug_importer_and_objs[0]
        assert bug_importer.bug_parser is bugimporters.bugzilla.KDEBugzilla

class TestBugzillaBugImporter(object):
    def assert_(self, a):
        assert a
    def assertEqual(self, a, b):
        assert a == b

    def setup_class(cls):
        # Set up the BugzillaTrackerModels that will be used here.
        cls.tm = dict(
                tracker_name='Miro',
                base_url='http://bugzilla.pculture.org/',
                bug_project_name_format='{tracker_name}',
                bitesized_type='key',
                bitesized_text='bitesized',
                documentation_type='key',
                documentation_text='',
                bugimporter='bugzilla',
                queries=[
                'http://bugzilla.pculture.org/buglist.cgi?bug_status=NEW&bug_status=ASSIGNED&bug_status=REOPENED&field-1-0-0=bug_status&field-1-1-0=product&field-1-2-0=keywords&keywords=bitesized&product=Miro&query_format=advanced&remaction=&type-1-0-0=anyexact&type-1-1-0=anyexact&type-1-2-0=anywords&value-1-0-0=NEW%2CASSIGNED%2CREOPENED&value-1-1-0=Miro&value-1-2-0=bitesized',
                ],
                )
        spider = bugimporters.main.BugImportSpider()
        spider.input_data = [cls.tm]
        bug_importer_and_objs = list(spider.get_bugimporters())
        assert len(bug_importer_and_objs) == 1
        obj, bug_importer = bug_importer_and_objs[0]
        cls.bug_importer = bug_importer

    def test_top_to_bottom(self):
        spider = bugimporters.main.BugImportSpider()
        spider.input_data = [self.tm]
        url2filename = {
            self.tm['queries'][0]:
                sample_data_path('pculture-bitesized-query.html'),
            'http://bugzilla.pculture.org/show_bug.cgi?ctype=xml&excludefield=attachmentdata&id=2138&id=2283&id=2374&id=4763&id=8462&id=8489&id=8670&id=9339&id=9415&id=9466&id=9569&id=11882&id=13122&id=15672&':
                sample_data_path('lots-of-pculture-bugs.xml'),
            }
        ar = autoresponse.Autoresponder(url2filename=url2filename,
                                        url2errors={})
        items = ar.respond_recursively(spider.start_requests())
        assert len(items) == 14
        assert set([item['canonical_bug_link'] for item in items]) == set([
                'http://bugzilla.pculture.org/show_bug.cgi?id=2283',
                'http://bugzilla.pculture.org/show_bug.cgi?id=2138',
                'http://bugzilla.pculture.org/show_bug.cgi?id=13122',
                'http://bugzilla.pculture.org/show_bug.cgi?id=9415',
                'http://bugzilla.pculture.org/show_bug.cgi?id=9569',
                'http://bugzilla.pculture.org/show_bug.cgi?id=15672',
                'http://bugzilla.pculture.org/show_bug.cgi?id=11882',
                'http://bugzilla.pculture.org/show_bug.cgi?id=2374',
                'http://bugzilla.pculture.org/show_bug.cgi?id=4763',
                'http://bugzilla.pculture.org/show_bug.cgi?id=9339',
                'http://bugzilla.pculture.org/show_bug.cgi?id=8670',
                'http://bugzilla.pculture.org/show_bug.cgi?id=8462',
                'http://bugzilla.pculture.org/show_bug.cgi?id=8489',
                'http://bugzilla.pculture.org/show_bug.cgi?id=9466',
                ])

    def test_provide_existing_bug_urls(self):
        spider = bugimporters.main.BugImportSpider()
        spider.input_data = [dict(self.tm)]
        # Add some existing bug URLs to the story
        spider.input_data[0]['existing_bug_urls'] = [
                'http://bugzilla.pculture.org/show_bug.cgi?id=9415',
                'http://bugzilla.pculture.org/show_bug.cgi?id=9569',
                'http://bugzilla.pculture.org/show_bug.cgi?id=15672',
                'http://bugzilla.pculture.org/show_bug.cgi?id=11882',
                'http://bugzilla.pculture.org/show_bug.cgi?id=2374',
                'http://bugzilla.pculture.org/show_bug.cgi?id=4763',
                ]
        spider.input_data[0]['queries'] = []
        url2filename = {
            'http://bugzilla.pculture.org/show_bug.cgi?ctype=xml&excludefield=attachmentdata&id=2374&id=4763&id=9415&id=9569&id=11882&id=15672&':
                sample_data_path('fewer-pculture-bugs.xml'),
            }
        ar = autoresponse.Autoresponder(url2filename=url2filename,
                                        url2errors={})
        items = ar.respond_recursively(spider.start_requests())
        assert len(items) == 6
        assert set([item['canonical_bug_link'] for item in items]) == set(
            spider.input_data[0]['existing_bug_urls'])

    def test_miro_bug_object(self):
        # Check the number of Bugs present.
        # Parse XML document as if we got it from the web
        with open(sample_data_path('miro-2294-2009-08-06.xml')) as f:
            all_bugs = list(self.bug_importer.handle_bug_xml(f.read()))

        assert len(all_bugs) == 1
        bug = all_bugs[0]
        self.assertEqual(bug['_project_name'], 'Miro')
        self.assertEqual(bug['title'], "Add test for torrents that use gzip'd urls")
        self.assertEqual(bug['description'], """This broke. We should make sure it doesn't break again.
Trac ticket id: 2294
Owner: wguaraldi
Reporter: nassar
Keywords: Torrent unittest""")
        self.assertEqual(bug['status'], 'NEW')
        self.assertEqual(bug['importance'], 'normal')
        self.assertEqual(bug['people_involved'], 5)
        self.assertEqual(bug['date_reported'], datetime.datetime(2006, 6, 9, 12, 49).isoformat())
        self.assertEqual(bug['last_touched'], datetime.datetime(2008, 6, 11, 23, 56, 27).isoformat())
        self.assertEqual(bug['submitter_username'], 'nassar@pculture.org')
        self.assertEqual(bug['submitter_realname'], 'Nick Nassar')
        self.assertEqual(bug['canonical_bug_link'], 'http://bugzilla.pculture.org/show_bug.cgi?id=2294')
        self.assert_(bug['good_for_newcomers'])

    def test_full_grab_miro_bugs(self):
        with open(sample_data_path('miro-2294-2009-08-06.xml')) as f:
            all_bugs = list(self.bug_importer.handle_bug_xml(f.read()))

        self.assertEqual(len(all_bugs), 1)
        bug = all_bugs[0]
        self.assertEqual(bug['canonical_bug_link'],
                         'http://bugzilla.pculture.org/show_bug.cgi?id=2294')
        self.assert_(not bug['looks_closed'])

    def test_miro_bugzilla_detects_closedness(self):
        # Parse XML document as if we got it from the web
        with open(sample_data_path('miro-2294-2009-08-06.xml')) as f:
            bug_xml = f.read()
            modified_bug_xml = bug_xml.replace('NEW', 'CLOSED')
            all_bugs = list(self.bug_importer.handle_bug_xml(modified_bug_xml))

        self.assertEqual(len(all_bugs), 1)
        bug = all_bugs[0]
        self.assertEqual(bug['canonical_bug_link'],
                         'http://bugzilla.pculture.org/show_bug.cgi?id=2294')
        self.assert_(bug['looks_closed'])

    def test_full_grab_resolved_miro_bug(self):
        # Parse XML document as if we got it from the web
        with open(sample_data_path('miro-2294-2009-08-06-RESOLVED.xml')) as f:
            all_bugs = list(self.bug_importer.handle_bug_xml(f.read()))

        self.assertEqual(len(all_bugs), 1)
        bug = all_bugs[0]
        self.assertEqual(bug['canonical_bug_link'],
                         'http://bugzilla.pculture.org/show_bug.cgi?id=2294')
        self.assert_(bug['looks_closed'])
