# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class YcCompanyItem(scrapy.Item):
    # define the fields for your item here like:
    company_name = scrapy.Field()
    company_website = scrapy.Field()
    founders_name = scrapy.Field()
    founders_linkedin = scrapy.Field()
    founders_twitter = scrapy.Field()

