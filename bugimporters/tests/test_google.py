import csv
import os
import mock

from bugimporters import google


HERE = os.path.dirname(os.path.abspath(__file__))


class TestGoogleURLUtilsTestCase(object):

    def test_google_name_from_url(self):
        retval = google.google_name_from_url('http://code.google.com/p/foo')
        assert 'foo' == retval

    def test_google_bug_detail_url(self):
        expected = 'https://code.google.com/p/foo/issues/detail?id=1'
        assert expected == google.google_bug_detail_url('foo', 1)


class TestGoogleBugImporter(object):

    def setup_method(self, method):
        self.tracker_model = mock.Mock()
        self.importer = google.GoogleBugImporter(self.tracker_model)

        self.response = mock.Mock()
        self.response.body = 'foobar'
        self.response.meta = {'issue': ''}
        self.response.request.url = 'http://code.google.com/p/myproj'

    @mock.patch('bugimporters.google.scrapy.http')
    def test_process_queries(self, scrapy):
        queries = ['http://example.com']
        retval = list(self.importer.process_queries(queries))

        expected_call_kwargs = {
            'url': queries[0],
            'callback': self.importer.handle_query_csv,
        }

        request = retval[0]
        scrapy.Request.assert_called_with(**expected_call_kwargs)

    def test_handle_query_csv(self):
        with mock.patch.object(self.importer, 'prepare_bug_urls') as prep:
            self.importer.handle_query_csv(self.response)
            args, kwargs = prep.call_args_list[0]
            assert args[0] == 'myproj'
            assert isinstance(args[1], csv.DictReader)

    @mock.patch('bugimporters.google.scrapy.http')
    def test_process_bugs(self, scrapy):
        bug_list = [
            ('http://code.google.com/p/foo/issues/detail?id=1', {}),
        ]

        retval = list(self.importer.process_bugs(bug_list))

        expected_call_kwargs = {
            'url': bug_list[0][0],
            'meta': {'issue': bug_list[0][1]},
            'callback': self.importer.handle_bug_html,
        }

        request = retval[0]
        scrapy.Request.assert_called_with(**expected_call_kwargs)

    def test_create_bug_dict_from_csv(self):
        project = 'myproj'
        csv_data = [
            {'ID': '1', 'foo': 'bar'},
            {'ID': '2', 'foo': 'baz'},
            {'ID': '3', 'foo': 'qux'},
        ]

        expected = {
            'https://code.google.com/p/myproj/issues/detail?id=1': csv_data[0],
            'https://code.google.com/p/myproj/issues/detail?id=2': csv_data[1],
            'https://code.google.com/p/myproj/issues/detail?id=3': csv_data[2],
        }

        retval = self.importer._create_bug_dict_from_csv(project, csv_data)

        assert len(retval) == 3
        assert retval == expected

    @mock.patch('bugimporters.google.scrapy.http')
    def test_create_bug_dict_from_csv_handles_paging(self, scrapy):
        project = 'myproj'
        example_line = ("This file is truncated to 100 out of 636 total "
                        "results. See https://example.com/ for the next set "
                        "of results.")
        csv_data = [{'ID': example_line}]

        self.importer._create_bug_dict_from_csv(project, csv_data)

        expected_call_kwargs = {
            'url': 'https://example.com/',
            'callback': self.importer.handle_query_csv,
        }

        scrapy.Request.assert_called_with(**expected_call_kwargs)

    def test_create_bug_dict_from_csv_just_these_urls(self):
        just_these = ['https://code.google.com/p/myproj/issues/detail?id=1',
                      'https://code.google.com/p/myproj/issues/detail?id=2']

        project = 'myproj'
        csv_data = [
            {'ID': '1', 'foo': 'bar'},
            {'ID': '2', 'foo': 'baz'},
            {'ID': '3', 'foo': 'qux'},
        ]

        expected = {
            'https://code.google.com/p/myproj/issues/detail?id=1': csv_data[0],
            'https://code.google.com/p/myproj/issues/detail?id=2': csv_data[1],
        }

        retval = self.importer._create_bug_dict_from_csv(project,
                                                         csv_data,
                                                         just_these)

        assert len(retval) == 2
        assert retval == expected

    def test_handle_bug_html(self):

        with mock.patch.object(google.GoogleBugParser, 'parse') as parse:
            self.importer.handle_bug_html(self.response)
            parse.assert_called_with(self.tracker_model)

    def test_prepare_bug_urls(self):
        project = 'myproj'
        csv_data = [{'ID': 1, 'foo': 'bar'}]

        with mock.patch.object(self.importer, '_create_bug_dict_from_csv') \
                as create_dict:
            with mock.patch.object(self.importer, 'process_bugs') \
                    as process_bugs:
                create_dict.return_value = {'foo': 'bar'}
                process_bugs.return_value = [1, 2, 3]

                retval = list(self.importer.prepare_bug_urls(project,
                                                             csv_data))
                assert retval == [1, 2, 3]

    def test_prepare_bug_urls_yields_noops(self):
        project = 'myproj'
        csv_data = [{'ID': '1', 'foo': 'bar'}]
        just_these = ['baz']

        with mock.patch.object(self.importer, '_create_bug_dict_from_csv') \
                as create_dict:
            with mock.patch.object(self.importer, 'process_bugs') \
                    as process_bugs:
                create_dict.return_value = {'foo': 'bar'}
                process_bugs.return_value = [1]

                retval = list(self.importer.prepare_bug_urls(project,
                                                             csv_data,
                                                             just_these))
                assert len(retval) == 2
                assert retval[1]['canonical_bug_link'] == 'baz'
                assert retval[1]['_no_update']


class TestGoogleBugParser(object):

    def setup_method(self, method):
        self.tracker_model = mock.Mock(tracker_name='myproj',
                                       bitesized_text='Easy',
                                       bitesized_type='',
                                       documentation_text='Docs',
                                       documentation_type='')

        self.response = mock.Mock()
        self.response.body = 'foobar'
        self.response.meta = {'issue': {}}
        self.response.request.url = 'http://code.google.com/p/myproj'

        self.parser = google.GoogleBugParser(self.response)

    def test_count_people_involved(self):
        self.parser.bug_data.update({
            'Reporter': 'foo',
            'Owner': 'bar',
            'Cc': 'foo, bar, baz, qux',
        })

        assert 4 == self.parser._count_people_involved()

    def test_parse_labels(self):
        self.parser.bug_data['AllLabels'] = 'foo, bar, baz'
        assert ['foo', 'bar', 'baz'] == self.parser._parse_labels()

    def test_parse_labels_ignores_type_tags(self):
        self.parser.bug_data['AllLabels'] = 'type-foo, name-bar, baz'
        assert ['baz'] == self.parser._parse_labels()

    def test_parse_description(self):
        example = os.path.join(HERE,
                               'sample-data',
                               'google',
                               'issue-detail.html')
        self.response.body = open(example, 'r').read()

        expected = ("Implement plus and minus infty, sign(x) doesn't work for "
                    "-infty... The\nlimit code should handle +-infty "
                    "correctly.")

        assert expected == self.parser._parse_description()

    def test_parse_description_removes_child_html_elements(self):
        example = os.path.join(HERE,
                               'sample-data',
                               'google',
                               'issue-detail-with-html.html')
        self.response.body = open(example, 'r').read()

        # We just need to be concerned on whether or not the test removes
        # child html, so check startswith will suffice since the example
        # data starts with a link
        expected = "https://gist.github.com/2660237"

        assert self.parser._parse_description().startswith(expected)

    def test_parse(self):
        # Get sample response data
        example = os.path.join(HERE,
                               'sample-data',
                               'google',
                               'issue-detail.html')
        self.response.body = open(example, 'r').read()

        # Get CSV contents of issue data for testing
        csv_file = os.path.join(HERE,
                                'sample-data',
                                'google',
                                'mock-issues-1.csv')

        reader = csv.DictReader(open(csv_file, 'r'))
        self.parser.bug_data = list(reader)[0]

        # Data we expect
        expected = {
            'title': 'setup/teardown support',
            'description': ("Implement plus and minus infty, sign(x) doesn't "
                            "work for -infty... The\nlimit code should handle "
                            "+-infty correctly."),
            'status': 'Accepted',
            'importance': 'Low',
            'people_involved': 1,
            'date_reported': '2010-06-10T09:49:27',
            'last_touched': '2013-11-14T11:15:03',
            'submitter_username': 'kon...@gmail.com',
            'submitter_realname': '',
            'canonical_bug_link': self.parser.bug_url,
            '_project_name': 'myproj',
            '_tracker_name': 'myproj',
            'looks_closed': False,
            'good_for_newcomers': False,
            'concerns_just_documentation': False,
        }

        assert expected == self.parser.parse(self.tracker_model)

    def test_parse_labels_bitesized(self):
        self.tracker_model.bitesized_type = 'Label'
        self.tracker_model.bitesized_text = 'Easy'

        # Get sample response data
        example = os.path.join(HERE,
                               'sample-data',
                               'google',
                               'issue-detail.html')
        self.response.body = open(example, 'r').read()

        # Get CSV contents of issue data for testing
        csv_file = os.path.join(HERE,
                                'sample-data',
                                'google',
                                'mock-issues-1.csv')

        reader = csv.DictReader(open(csv_file, 'r'))
        self.parser.bug_data = list(reader)[1]

        bug = self.parser.parse(self.tracker_model)
        assert bug['good_for_newcomers']

    def test_parse_labels_documentation(self):
        self.tracker_model.documentation_type = 'Label'
        self.tracker_model.bitesized_text = 'Docs'

        # Get sample response data
        example = os.path.join(HERE,
                               'sample-data',
                               'google',
                               'issue-detail.html')
        self.response.body = open(example, 'r').read()

        # Get CSV contents of issue data for testing
        csv_file = os.path.join(HERE,
                                'sample-data',
                                'google',
                                'mock-issues-1.csv')

        reader = csv.DictReader(open(csv_file, 'r'))
        self.parser.bug_data = list(reader)[2]

        bug = self.parser.parse(self.tracker_model)
        assert bug['concerns_just_documentation']
