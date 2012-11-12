#!/usr/bin/env python
import argparse
import sys
import yaml
import importlib
import scrapy.spider
import logging
import scrapy.cmdline

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
    ret.as_appears_in_distribution = ''# FIXME, hack
    return ret

def main(raw_arguments):
    parser = argparse.ArgumentParser(description='Simple oh-bugimporters crawl program')

    parser.add_argument('-i', action="store", dest="input")
    parser.add_argument('-o', action="store", dest="output")
    args = parser.parse_args(raw_arguments)

    args_for_scrapy = ['scrapy',
                       'runspider',
                       'bugimporters/main.py',
                       '-a', 'input_filename=%s' % (args.input,),
                       '-s', 'TELNETCONSOLE_ENABLED=0',
                       '-s', 'WEBSERVICE_ENABLED=0',
                       '-s', 'FEED_FORMAT=jsonlines',
                       '-s', 'FEED_URI=%s' % (args.output,),
                       '-s', 'CONCURRENT_REQUESTS_PER_DOMAIN=1',
                       '-s', 'CONCURRENT_REQUESTS=200',
                       '-s', 'DEPTH_PRIORITY=1',
                       '-s', 'SCHEDULER_DISK_QUEUE=scrapy.squeue.PickleFifoDiskQueue',
                       '-s', 'SCHEDULER_MEMORY_QUEUE=scrapy.squeue.FifoMemoryQueue',
                       ]
    return scrapy.cmdline.execute(args_for_scrapy)


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
