#!/usr/bin/env python
import argparse
import sys
import yaml
import mock
import importlib

def dict2obj(d):
    class Trivial(object):
        def get_base_url(self):
            return self.base_url
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

        module, class_name = obj.bugimporter.split('.', 1)
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
        class StupidQuery(object):
            def __init__(self, url):
                self.url = url
            def get_query_url(self):
                return self.url
            def save(*args, **kwargs):
                pass # FIXME: Hack
        queries = [StupidQuery(q) for q in obj.queries]
        bug_importer.process_queries(queries)
        all_bug_data.extend(bug_data)

    # FIXME: Hack
    # Remove the tracker attribute from the exported data, because we
    # cannot export that content to properly to YAML.
    for bug in all_bug_data:
        if 'tracker' in bug:
            bug['tracker'] = None

    return [dict(x) for x in all_bug_data]

if __name__ == '__main__':
    main(sys.argv[1:])
