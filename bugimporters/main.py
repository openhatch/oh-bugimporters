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
    parser.add_argument('--extended-scrape', action="store_const", dest="extended_scrape", const=1, default=0)
    args = parser.parse_args(raw_arguments)


    args_for_scrapy = ['scrapy',
                       'runspider',
                       'bugimporters/main.py',
                       '-a', 'input_filename=%s' % (args.input,),
                       '-s', 'TELNETCONSOLE_ENABLED=0',
                       '-s', 'BOT_NAME=oh-bugimporters',
                       '-s', 'USER_AGENT=oh-bugimporters',
                       '-s', 'WEBSERVICE_ENABLED=0',
                       '-s', 'FEED_FORMAT=jsonlines',
                       '-s', 'FEED_URI=%s' % (args.output,),
                       '-s', 'CONCURRENT_REQUESTS_PER_DOMAIN=1',
                       '-s', 'CONCURRENT_REQUESTS=200',
                       '-s', 'DEPTH_PRIORITY=1',
                       '-s', 'DOWNLOAD_DELAY=0.5',  # per host
                       '-s', 'SCHEDULER_DISK_QUEUE=scrapy.squeue.PickleFifoDiskQueue',
                       '-s', 'SCHEDULER_MEMORY_QUEUE=scrapy.squeue.FifoMemoryQueue',
                       '-a', 'extended_scrape=%s' % (args.extended_scrape)
                       ]
    return scrapy.cmdline.execute(args_for_scrapy)

def grab_bugimporter_attribute_via_string(s):
    module, class_name = s.split('.', 1)
    bug_import_module = importlib.import_module('bugimporters.%s' % (
            module,))
    found_class = getattr(bug_import_module, class_name)
    return found_class

class BugImportSpider(scrapy.spider.BaseSpider):
    name = "Spider for importing using oh-bugimporters"

    def get_bugimporters(self):
        '''This method gets called after __init__() because sometimes
        we set the .input_data parameter after __init__() time.'''
        objs = []
        for d in self.input_data:
            objs.append(dict2obj(d))

        for obj in objs:
            bugimporter_aliases = {
                'trac': 'trac.TracBugImporter',
                'roundup': 'roundup.RoundupBugImporter',
                'github': 'github.GitHubBugImporter',
                'google': 'google.GoogleBugImporter',
                'jira': 'jira.JiraBugImporter',
                'launchpad': 'launchpad.LaunchpadBugImporter',
                'bugzilla': 'bugzilla.BugzillaBugImporter',
                'tigris': 'tigris.TigrisBugImporter',
                }

            raw_bug_importer = obj.bugimporter
            if '.' not in raw_bug_importer:
                raw_bug_importer = bugimporter_aliases[raw_bug_importer]

            bug_import_class = grab_bugimporter_attribute_via_string(
                raw_bug_importer)

            # The configuration may ask us to use a specific bug parser
            special_bug_parser_name = getattr(obj, 'custom_parser', '')
            if special_bug_parser_name:
                try:
                    bug_parser_class = grab_bugimporter_attribute_via_string(
                        special_bug_parser_name)
                except Exception, e:
                    # Log the error...
                    logging.error("FYI, this is not a valid custom parser: %s",
                                  special_bug_parser_name)
                    logging.exception(e)
                    # And keep looping, skipping this misconfigured bug importer
                    continue

            else:
                bug_parser_class = None
                # By passing None here, we ask the
                # BugImporter object to use its default.

            bug_importer = bug_import_class(
                obj, reactor_manager=None,
                bug_parser=bug_parser_class,
                extended_scrape=self.extended_scrape)
            yield (obj, bug_importer)

    def start_requests(self):
        for (obj, bug_importer) in self.get_bugimporters():
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

    def __init__(self, input_filename=None, extended_scrape=0):
        self.extended_scrape = int(extended_scrape)

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
