How this integrates with the main OpenHatch site
================================================

In this section of the oh-bugimporters documentation, we discuss how
the OpenHatch web app integrates with this "oh-bugimporters"
project. (If you want to integrate your own project with
oh-bugimporters, you can use this to understand the architecture.)

To understand that, we'll go through a few elements at a time.


Input configuration
===================

In order to run oh-bugimporters and actually download bugs, you must
configure a list of bug trackers that you want to pull data from.

The file should be a YAML file.

You can use a sample configuration file bundled in examples/sample_configuration.yaml.


Downloading with scrapy
=======================

The process of doing the actual downloading is done using the "scrapy"
command. Scrapy is a framework for running web crawlers, and you can
use it to run the bug importers.

If you have a virtualenv in which you have run "setup.py develop" for
this code in env/, the following command will run a scrapy-based import::

    env/bin/scrapy runspider bugimporters/main.py  -a input_filename=/tmp/input-configuration.yaml  -s FEED_FORMAT=json -s FEED_URI=/tmp/results.json  -s LOG_FILE=/tmp/scrapy-log -s CONCURRENT_REQUESTS_PER_DOMAIN=1 -s CONCURRENT_REQUESTS=200

Note that you must have a configuration file at /tmp/input-configuration.yaml
for this command to work. If you need a sample configuration file, copy it
out of examples/ as described above in the "Input configuration" section.


On the web: /customs/
=====================
Within the OpenHatch code, "customs" is the name for data "import" and
"export." (It's a pun.)

On the live OpenHatch website, there is a small bit of web code for
letting site administrators manage the list of bug trackers that we
download data from. This lives at https://openhatch.org/customs/

(A note about security: At the moment, there is no authorization; any
logged-in user of the OpenHatch site can visit the /customs/
management interface and change this configuration. Right now, we
consider this a good idea because it makes using the site a smooth
process -- whenever a project maintainer wants to add their project,
they don't need to wait to receive permission.)

The "Tracker type" drop-down is generated from data stored in
mysite/customs/core_bugimporters.py -- in particular, the all_trackers
object defined at the top of the file. As you choose options in the
drop-down, JavaScript on the page automatically submits the form and
shows you the list of bug trackers stored in the database that
correspond to that type of tracker.

By adjusting the information configured in this interface, project
maintainers alter the contents of the OpenHatch database (via models
and forms in mysite/customs/).

Once per day, the live OpenHatch site exports its data into an input
configuration file, and then it runs scrapy to actually download data
from the bug trackers in question.
