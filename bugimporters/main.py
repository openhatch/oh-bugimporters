#!/usr/bin/env python
import argparse
import sys
import yaml
import mock
import importlib
import scrapy.spider
import logging

def dict2obj(d):
    class Trivial(object):
        def get_base_url(self):
            ### HACK: If base_url doesn't end with a slash, let's make it
            ### end with a slash.
            ret = self.base_url
            if not ret.endswith('/'):
                ret += '/'
            return ret
    ret = Trivial()
    for thing in d:
        setattr(ret, thing, d[thing])
    ret.old_trac = False # FIXME, hack
    ret.max_connections = 5 # FIXME, hack
    ret.as_appears_in_distribution = ''# FIXME, hack
    return ret

class FakeReactorManager(object):
    def __init__(self):
        self.running_deferreds = 0 # FIXME: Hack
    def maybe_quit(self, *args, **kwargs): ## FIXME: Hack
        return

def main(raw_arguments):
    parser = argparse.ArgumentParser(description='Simple oh-bugimporters crawl program')

    parser.add_argument('-i', action="store", dest="input")
    parser.add_argument('-o', action="store", dest="output")
    args = parser.parse_args(raw_arguments)

    with open(args.input) as input_file:
        with open(args.output, 'w') as output_file:
            input_data = yaml.load(input_file)
            # Sometimes, the data we are given is wrapped in {'objects': data}
            # Detect that, and work around it.
            if 'data' in input_data:
                input_data = input_data['data']
            output = main_worker(input_data)
            yaml.safe_dump(output, output_file)

def main_worker(data):
    objs = []
    for d in data:
        objs.append(dict2obj(d))

    all_bug_data = []
    for obj in objs:
        bug_data = []
        def generate_bug_transit(bug_data=bug_data):
            def bug_transit(bug):
                bug_data.append(bug)
            return {'get_fresh_urls': lambda *args: {},
                    'update': bug_transit,
                    'delete_by_url': lambda *args: {}}

        bugimporter_aliases = {
            'trac': 'trac.TracBugImporter',
            'roundup': 'roundup.RoundupBugImporter',
            'github': 'github.GitHubBugImporter',
            'google': 'google.GoogleBugImporter',
            }

        raw_bug_importer = obj.bugimporter
        ### If the bugimporter value is not something we can use, skip it
        if (('.' in raw_bug_importer) or
            raw_bug_importer not in bugimporter_aliases):
            logging.error("Skipping one bug importer data object.")
            continue

        if '.' not in raw_bug_importer:
            raw_bug_importer = bugimporter_aliases[raw_bug_importer]

        module, class_name = raw_bug_importer.split('.', 1)
        bug_import_module = importlib.import_module('bugimporters.%s' % (
                module,))
        bug_import_class = getattr(bug_import_module, class_name)
        bug_importer = bug_import_class(
            obj, FakeReactorManager(),
            data_transits={'bug': generate_bug_transit(),
                           'trac': {
                    'get_bug_times': lambda url: (None, None),
                    'get_timeline_url': mock.Mock(),
                    'update_timeline': mock.Mock()
                    }})
        queries = obj.queries
        bug_importer.process_queries(queries)
        all_bug_data.extend(bug_data)

    # FIXME: Hack
    # Remove the tracker attribute from the exported data, because we
    # cannot export that content to properly to YAML.
    for bug in all_bug_data:
        if 'tracker' in bug:
            bug['tracker'] = None

    return [dict(x) for x in all_bug_data]


class BugImportSpider(scrapy.spider.BaseSpider):
    name = "Spider for importing using oh-bugimporters"

    def start_requests(self):
        objs = []
        for d in self.input_data:
            objs.append(dict2obj(d))

        for obj in objs:
            bugimporter_aliases = {
                'trac': 'trac.TracBugImporter',
                'roundup': 'roundup.RoundupBugImporter',
                'github': 'github.GitHubBugImporter',
                'google': 'google.GoogleBugImporter',
                }

            raw_bug_importer = obj.bugimporter
            if '.' not in raw_bug_importer:
                raw_bug_importer = bugimporter_aliases[raw_bug_importer]

            module, class_name = raw_bug_importer.split('.', 1)
            bug_import_module = importlib.import_module('bugimporters.%s' % (
                    module,))
            bug_import_class = getattr(bug_import_module, class_name)
            bug_importer = bug_import_class(
                obj, reactor_manager=None,
                data_transits=None)
            for request in bug_importer.process_queries(obj.queries):
                yield request

            older_bug_data_url = getattr(
                obj, 'get_older_bug_data', '')
            if older_bug_data_url:
                kwargs = {'older_bug_data_url': older_bug_data_url}
            else:
                kwargs = {}

            bug_urls = getattr(obj, 'existing_bug_urls', [])
            if hasattr(bug_importer, 'process_bugs'):
                if bug_urls:
                    for request in bug_importer.process_bugs(
                        [(url, None) for url in bug_urls],
                        **kwargs):
                        yield request
            else:
                logging.error("FYI, this bug importer does not support "
                              "process_bugs(). Fix it.")

    def __init__(self, input_filename=None):
        if input_filename is None:
            return

        with open(input_filename) as f:
            self.input_data = yaml.load(f)

        # Sometimes, the data we are given is wrapped in {'objects': data}
        # Detect that, and work around it.
        if 'objects' in self.input_data:
            self.input_data = self.input_data['objects']

if __name__ == '__main__':
    main(sys.argv[1:])
