Roadmap
=======

Right now, this package has the following functionality:

* Asynchronous bug fetching

* Pluggable support for new bug tracker types, and for special-cased
  BugParser objects

For the next release, I would expect the following goals:

* Very high coverage of the bugimporters code from within the
  test suite. (Note that most of the code actually *is* tested, but
  the tests haven't been moved over from oh-mainline.)

* Documentation on how to visualize the coverage.xml file from
  something other than Jenkins. (Perhaps there's an HTML report we can
  generate.)

For releases after that:

* Contacting the contributors and getting them to agree to the Apache
  License 2.0 for this code (or at least not AGPLv3; perhaps GPLv3 or
  LGPLv3; but my vote is for Apache License 2.0).

* Adding support for other bug tracking backends, such as
  sourceforge.net's Allura, and the older sourceforge.net tracker.

* Fixing the "old_trac" support to work again. (In the past, we relied
  on a Django model called TracBugTimes that stored the content of
  some RSS feeds. In oh-bugimporters, we can instead cache those RSS
  feeds on the filesystem somewhere, and thereby stop using the
  database as a cache.)

* Refactoring to use scrapy to manage the crawl, so we can delete all
  our messy async download management code.

* Documentation describing how to create a simple Python dict
  describing a bug tracker, and pass that through the machinery to get
  a dump of that bug tracker's bug data. (After the move to Scrapy,
  this should be fairly easy.)

Bugs
====

If you want to file specific bugs against this package, use the
main OpenHatch bug tracker. Please add the "bugimporters" tag.

Relevant links:

* `OpenHatch bug tracker`_
* `List of open bugs tagged as bugimporters`_

.. _OpenHatch bug tracker: https://openhatch.org/bugs/

.. _List of open bugs tagged as bugimporters: https://openhatch.org/bugs/issue?%40search_text=&title=&%40columns=title&milestone=&keyword=18&id=&%40columns=id&creation=&creator=&activity=&%40columns=activity&%40sort=activity&actor=&priority=&%40group=priority&status=&%40columns=status&assignedto=&%40columns=assignedto&%40pagesize=50&%40startwith=0&%40queryname=&%40old-queryname=&%40action=search
