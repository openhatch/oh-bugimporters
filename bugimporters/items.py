import scrapy.item

class ParsedBug(scrapy.item.Item):
    # Fields beginning with an underscore are not really part of a
    # bug, but extra information that can be exported.
    _project_name = scrapy.item.Field()
    _tracker_name = scrapy.item.Field()

    # These fields correspond to bug data
    title = scrapy.item.Field()
    description = scrapy.item.Field()
    status = scrapy.item.Field()
    importance = scrapy.item.Field()
    people_involved = scrapy.item.Field()
    date_reported = scrapy.item.Field()
    last_touched = scrapy.item.Field()
    submitter_username = scrapy.item.Field()
    submitter_realname = scrapy.item.Field()
    canonical_bug_link = scrapy.item.Field()
    looks_closed = scrapy.item.Field()
    last_polled = scrapy.item.Field()
    as_appears_in_distribution = scrapy.item.Field()
    good_for_newcomers = scrapy.item.Field()
    concerns_just_documentation = scrapy.item.Field()
