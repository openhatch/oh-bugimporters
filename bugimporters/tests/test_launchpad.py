import autoresponse
import bugimporters.main
import os.path
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))

class TestLaunchpadBugImporter(object):

    @staticmethod
    def assertEqual(thing1, thing2):
        assert thing1 == thing2

    def setup_class(cls):
        cls.tm = dict(
            tracker_name='bzr',
            launchpad_name='bzr',
            bitesized_tag='easy',
            documentation_tag='doc',
            queries=[
                'https://api.launchpad.net/1.0/bzr/?ws.op=searchTasks',
                ],
            bugimporter='launchpad.LaunchpadBugImporter',
            )

    def test_top_to_bottom(self, extra_url2filename=None):
        spider = bugimporters.main.BugImportSpider()
        spider.input_data = [self.tm]
        url2filename = {
            'https://api.launchpad.net/1.0/bzr/?ws.op=searchTasks':
                os.path.join(HERE, 'sample-data', 'launchpad',
                             'bzr?ws.op=searchTasks'),
            'https://api.launchpad.net/1.0/bugs/839461':
                os.path.join(HERE, 'sample-data', 'launchpad',
                             'bugs_839461'),
            'https://api.launchpad.net/1.0/bugs/839461/subscriptions':
                os.path.join(HERE, 'sample-data', 'launchpad',
                             'bugs_839461_subscriptions'),
            'https://api.launchpad.net/1.0/~vila':
                os.path.join(HERE, 'sample-data', 'launchpad',
                             '~vila'),
            }
        if extra_url2filename:
            url2filename.update(extra_url2filename)

        ar = autoresponse.Autoresponder(url2filename=url2filename,
                                        url2errors={})
        items = ar.respond_recursively(spider.start_requests())
        assert len(items) == 1
        item = items[0]

        self.assertEqual(datetime.datetime(2011, 9, 2, 10, 42, 43, 883929).isoformat(),
                         item['date_reported'])
        self.assertEqual(u'Bug #839461 in Bazaar: "can\'t run selftest for 2.2 with recent subunit/testtools"', item['title'])
        self.assertEqual('Critical', item['importance'])
        self.assertEqual('https://bugs.launchpad.net/bzr/+bug/839461',
                         item['canonical_bug_link'])

        self.assertEqual(
            datetime.datetime(2012, 8, 30, 14, 16, 26, 102504).isoformat(),
            item['last_touched'])
        self.assertEqual("While freezing bzr-2.2.5 from a natty machine with python-2.7.1+,\nlp:testtools revno 244 and lp:subunit revno 151 I wasn't able to\nrun 'make check-dist-tarball'.\n\nI had to revert to testtools-0.9.2 and subunit 0.0.6 and use\npython2.6 to successfully run:\n\n  BZR_PLUGIN_PATH=-site make check-dist-tarball PYTHON=python2.6 | subunit2pyunit\n\nAlso, I've checked the versions used on pqm:\n\n(pqm-amd64-new)pqm@cupuasso:~/pqm-workdir/bzr+ssh/new-pqm-test$ dpkg -l | grep subunit\nii  libsubunit-perl                                 0.0.6-1~bazaar1.0.IS.10.04            perl parser and diff for Subunit streams\nii  python-subunit                                  0.0.6-1~bazaar1.0.IS.10.04            unit testing protocol - Python bindings to g\nii  subunit                                         0.0.6-1~bazaar1.0.IS.10.04            command line tools for processing Subunit st\n(pqm-amd64-new)pqm@cupuasso:~/pqm-workdir/bzr+ssh/new-pqm-test$ dpkg -l | grep testtools\nii  python-testtools                                0.9.6-0~bazaar1.0.IS.8.04             Extensions to the Python unittest library",
                         item['description'])

        self.assertEqual(1, item['people_involved'])

        self.assertEqual('vila', item['submitter_username'])
        self.assertEqual('Vincent Ladeuil', item['submitter_realname'])
        return item

    def test_looks_closed_detection(self):
        extra_url2filename={
            'https://api.launchpad.net/1.0/bzr/?ws.op=searchTasks':
                os.path.join(HERE, 'sample-data', 'launchpad',
                             'bzr?ws.op=searchTasks.closed'),
            }
        item = self.test_top_to_bottom(extra_url2filename=extra_url2filename)
        assert item['looks_closed']

    def test_documentation_detection(self):
        extra_url2filename={
            'https://api.launchpad.net/1.0/bugs/839461':
                os.path.join(HERE, 'sample-data', 'launchpad',
                             'bugs_839461doc'),
            }
        item = self.test_top_to_bottom(extra_url2filename=extra_url2filename)
        assert item['concerns_just_documentation']

    def test_bitesize_detection(self):
        extra_url2filename={
            'https://api.launchpad.net/1.0/bugs/839461':
                os.path.join(HERE, 'sample-data', 'launchpad',
                             'bugs_839461bite'),
            }
        item = self.test_top_to_bottom(extra_url2filename=extra_url2filename)
        assert item['good_for_newcomers']
