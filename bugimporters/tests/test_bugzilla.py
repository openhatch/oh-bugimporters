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

class FakeDate(datetime.datetime):
    #Class to mock datetime.datetime.utcnow()
    @classmethod
    def utcnow(f):
        return f(2013, 10, 1)

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

            with mock.patch('datetime.datetime', FakeDate) as mock_date:
                data = kdebugzilla.get_parsed_data_dict(base_url='http://bugs.kde.org/',
                                                        bitesized_type=None,
                                                        bitesized_text='',
                                                        documentation_type=None,
                                                        documentation_text='')
                self.assertEqual(data['last_polled'], datetime.datetime(2013, 10, 1).isoformat())

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

    def test_with_kde_query_html(self):
        # handle_query_html() was crashing on input like this, so we
        # give it a sample from the KDE bug tracker.
        with open(sample_data_path('kde-junior-jobs-query.html')) as kde_html:
            all_bugs = self.bug_importer.handle_query_html(kde_html.read())

        # First, assert we don't crash. (-;
        # Second, make sure we got the right bug list out.
        assert set(all_bugs) == set([
                6602, 30332, 34894, 42227, 45585, 51843, 54864,
                55576, 56175, 57983, 60037, 60264, 60626, 61403,
                63015, 64143, 73759, 76849, 78950, 91970, 92906,
                94948, 96727, 97055, 97399, 98654, 101063,
                102276, 104666, 105139, 107083, 111672, 115637,
                117717, 118507, 130575, 132347, 133133, 138027,
                138302, 138685, 139201, 139293, 139389, 140403,
                140434, 141051, 142563, 144534, 149453, 150575,
                151369, 152182, 156484, 156653, 162685, 163620,
                164759, 165747, 168036, 176389, 176813, 179066,
                180712, 182843, 187217, 187298, 187300, 192427,
                193989, 195278, 198661, 199509, 199691, 200157,
                201416, 205509, 206383, 206385, 206481, 207828,
                208047, 208302, 208947, 209418, 211669, 215676,
                215783, 217881, 218992, 219102, 220588, 221021,
                221107, 221602, 223616, 230071, 230129, 232098,
                232357, 236583, 238687, 240198, 240409, 240983,
                242829, 243805, 244641, 245705, 246232, 250452,
                250856, 252420, 254404, 256064, 260020, 260022,
                260161, 260164, 260352, 263766, 266052, 268163,
                269768, 272912, 273385, 274299, 276023, 277635,
                278376, 278497, 279861, 282518, 283624, 284459,
                287027, 287355, 287399, 288323, 288556, 288562,
                289306, 289348, 289647, 291500, 291709, 292197,
                292396, 292935, 294268, 294388, 294478, 295170,
                295318, 296049, 296532, 297820, 297830, 299218,
                299317, 300063, 300184, 300306, 300979, 303382,
                303665, 303668, 304094, 304274, 305297, 305661,
                305758, 306288, 306650, 306853, 307094, 307864,
                308345, 308913, 309050, 309428, 309724, 309739,
                309819, 310051, 310052, 310053, 310181, 310182])

    def test_with_bug_xml_containig_errors(self):
        with open(sample_data_path("some-bugs-with-errors.xml")
                  ) as kde_bug_xml_data:
            bug_data = list(
                self.bug_importer.handle_bug_xml(kde_bug_xml_data.read()))

        # Even though we queried for two bugs, one is filtered out.
        assert len(bug_data) == 1

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

    def test_tracking_bug_xml(self):
        with open(sample_data_path('fedora-tracking-bug.xml')) as f:
            all_bugs = list(self.bug_importer.handle_tracking_bug_xml(f.read()))

        assert set(all_bugs) == set([
                469416, 499203, 509837, 510021, 510026, 510029,
                510030, 510043, 510051, 510057, 510059, 510062,
                510065, 510072, 510074, 510080, 510082, 510084,
                510085, 510089, 510090, 510095, 510109, 510123,
                510125, 510145, 510730, 511270, 511282, 512962,
                512968, 512984, 512988, 515302, 515303, 515306,
                515311, 516739, 516756, 516776, 516783, 516801,
                516807, 516808, 516986, 517006, 517007, 517528,
                518007, 518012, 518020, 518026, 518030, 518031,
                518045, 518065, 518070, 518304, 525810, 591370])

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
