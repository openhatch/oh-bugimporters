About this project
==================

The OpenHatch bug importers code is a standalone Python package,
independent of Django or other web application dependencies, that can
download and process information from bug trackers across the web.

Its main intended use is as part of collecting data for the
OpenHatch.org "volunteer opportunity finder," but if you find it
useful, please go ahead and use it for another purpose! We do
cheerfully accept changes.

This package is maintained by the OpenHatch community, so when you
want to share code with us, you'll probably want to read the
`OpenHatch patch contribution guide`_.

.. _OpenHatch patch contribution guide: http://openhatch.readthedocs.org/en/latest/contributor/handling_patches.html

Installation
============

If you want to use oh-bugimporters as a standalone Python package,
which is the recommended way to develop it, you'll need to run the
following commands in your command prompt/terminal emulator.

Get the code:

1. ``git clone https://github.com/openhatch/oh-bugimporters.git``

Switch into its directory:

2. ``cd oh-bugimporters``

Create a virtualenv for the project. (On Debian/Ubuntu systems, you'll
need to run "apt-get install python-virtualenv" before this will work.)

3. ``virtualenv env``

Tell the virtualenv we want to "develop" this app, which also has the
side-effect of downloading and installing any dependencies.

4. Install compile-time dependences

If on Debian or Ubuntu, run::

 sudo apt-get install libxml2-dev
 sudo apt-get build-dep python-lxml
 sudo apt-get install libffi-dev

If on Windows or Mac OS, then you might run into some errors. If you
get it working there, please let us know what commands make it work on
those platforms.

5. ``env/bin/python setup.py develop``

*Note*: If you run into a problem involving Scrapy and "uses_query", then you are hitting a `bug involving Python 2.7.3 and scrapy`_. In that case, you should make the virtualenv again with Python 2.6::

    virtualenv -p python2.6 env

After you re-create the virtualenv, you should run the "develop"
command listed in step 4 again, and now you won't get an error, so you
can continue.

.. _bug involving Python 2.7.3 and scrapy: https://github.com/scrapy/scrapy/issues/144

Finally, install a few optional dependencies:

6. ``env/bin/pip install -r devrequirements.txt``

Running the test suite
======================

This set of code comes with a set of automated tests that verify the
behavior of the code. We like to keep the code in a clean state where
all of those tests pass.

You can run them as so::

  env/bin/py.test

You will see a bunch of output that indicates the "pytest" system is
looking for, finding, and running tests. Each "." (dot) character
indicates a test that passed.

The code generates a coverage.xml file that with information to help
understand which parts of the code are "covered" by the test suite. You
can read `more about code coverage`_.

.. _more about code coverage: https://en.wikipedia.org/wiki/Code_coverage

License
=======

Right now, the code is under the AGPLv3 license. We should probably,
one day, move it to be under the Apache License 2.0 or another more
permissive license.

Basic concepts
==============

This Python package has the following basic components:

* BugImporter classes, which *download* bug data from remote bug trackers.

* BugParser classes, which *process* bug data after the download and normalize it into simple items.

* The ParsedBug object (in bugimporters/items.py), which is what all bug data from the 'net eventually becomes.

The BugImporter class has a bunch of machinery for doing the
downloading in parallel. However, the development community around
this project thinks that we should remove that machinery and switch to
depending on "Scrapy" and using that for downloading.

In the bugimporters/ directory, you will find one Python file per
different type of bug tracker supported by this codebase, along with
some helper files.

To add support for a new bug tracker
====================================

Generally, every bug tracker supported by this codebase must provide:

* A subclass of BugImporter, and
* A subclass of BugParser.

The difference is that the BugImporter subclass is designed to accept
a list of bug numbers and perform a bunch of HTTP requests to download
information about the bug. In this sense, a BugImporter is aware of
the network. BugParser objects are unaware of the network.

Generally, one usually only needs a single BugParser and BugImporter
subclass per *type* of bug tracker that is supported. For example,
bugimporters/github.py contains one BugImporter subclass that manages
the downloading of data via the Github API, and it contains one
BugParser subclass that converts data from that API into instances of
bugimporters.items.ParsedBug, massaging data as necessary.

(Note that it is possible to write a BugImporter that generates the
ParsedBug objects without a BugParser... in theory. We don't recommend
doing things this way, but bugimporters/google.py is an example of one.)

The role of multiple BugParsers
===============================

A BugImporter, by default, uses one particular BugParser to process
bug data.  For example, the Bugzilla bug importer has a generic
Bugzilla parser that processes the XML data that Bugzilla returns.

The Bugzilla bug importer is an example of a BugImporter that can work
with any of a few different BugParser subclasses. You can see those in
bugimporters/bugzilla.py.

This is usually helpful when a specific open source community uses its
bug tracker in some unusual way, and therefore special code is
required to massage the data into the format of a
bugimporters.items.ParsedBug. (For an example, see
bugimporters/bugzilla.py and the KDEBugzilla class -- in particular,
the generate_bug_project_name() method. This method exists because the
KDE communities names projects in ways that we want to smooth out for
consumers of the data, such as the OpenHatch website.)

If you want to add a new custom BugParser, here is what you would do:

* Find the file corresponding to the bug tracker *type* you're adding
  a custom bug parser for. For example, if you're adding support for a
  special Bugzilla instance, open up bugimporters/bugzilla.py in your
  favorite text editor.

* Add a new subclass of BugParser at the bottom of that file, probably
  overriding the extract_tracker_specific_data method. Make sure to
  subclass from the specific version of BugParser to the kind of bug
  tracker you're modifying; for example, if you are adding custom code
  for a special Bugzilla withi bugimporters/bugzilla.py, your new
  class should be a subclass of BugzillaBugParser.

* Write a test. For now, this package only has tests covering the Trac
  bug importers and parsers. If you're adding a new bug parser for Trac,
  simply:

  * Copy the test_bug_parser() into a new method

  * Change the sample data, and the assertions, for the behavior you need.

  * Run the new test. Make sure it fails.

  * Now, write a new BugParser subclass that impements the behavior you need.

  * Make sure the test passes. (Then submit it for review and inclusion!)

By focusing on this test-driven workflow, you are sure that the code
you add is required and correct.
