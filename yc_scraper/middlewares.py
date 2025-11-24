# Define here the models for your spider middleware
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/spider-middleware.html

from scrapy import signals
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from scrapy.http import HtmlResponse
import time


class YcScraperSpiderMiddleware:
    """Spider middleware for YC scraper"""

    @classmethod
    def from_crawler(cls, crawler):
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_input(self, response, spider):
        return None

    def process_spider_output(self, response, result, spider):
        for i in result:
            yield i

    def process_spider_exception(self, response, exception, spider):
        pass

    def process_start_requests(self, start_requests, spider):
        for r in start_requests:
            yield r

    def spider_opened(self, spider):
        spider.logger.info('Spider opened: %s' % spider.name)


class YcScraperDownloaderMiddleware:
    """Downloader middleware for YC scraper"""

    @classmethod
    def from_crawler(cls, crawler):
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request, spider):
        return None

    def process_response(self, request, response, spider):
        return response

    def process_exception(self, request, exception, spider):
        pass

    def spider_opened(self, spider):
        spider.logger.info('Spider opened: %s' % spider.name)


class SeleniumMiddleware:
    """Middleware to handle JavaScript-rendered pages using Selenium"""

    def __init__(self):
        self.driver = None
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
        except Exception as e:
            # If Chrome is not available, try Firefox
            try:
                from selenium.webdriver.firefox.options import Options as FirefoxOptions
                firefox_options = FirefoxOptions()
                firefox_options.add_argument('--headless')
                self.driver = webdriver.Firefox(options=firefox_options)
            except Exception as e2:
                print(f"Error initializing browser drivers: {e}, {e2}")
                raise

    @classmethod
    def from_crawler(cls, crawler):
        middleware = cls()
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        return middleware

    def process_request(self, request, spider):
        # Only use Selenium for the companies listing page (which has infinite scroll)
        # Skip Selenium for individual company pages - they're mostly static HTML
        is_listing_page = '/companies?' in request.url or request.url.endswith('/companies')
        
        if is_listing_page and 'ycombinator.com' in request.url and self.driver:
            spider.logger.info(f'Processing listing page {request.url} with Selenium')
            try:
                self.driver.get(request.url)
                
                # Wait for content to load
                time.sleep(1)
                
                # Scroll to load more content (infinite scroll)
                last_height = self.driver.execute_script("return document.body.scrollHeight")
                scroll_attempts = 0
                max_scrolls = 10  # Reduced scroll attempts
                
                while scroll_attempts < max_scrolls:
                    # Scroll down
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(0.5)  # Reduced wait time
                    
                    # Calculate new scroll height
                    new_height = self.driver.execute_script("return document.body.scrollHeight")
                    if new_height == last_height:
                        break
                    last_height = new_height
                    scroll_attempts += 1
                
                # Get page source after scrolling
                body = self.driver.page_source
                return HtmlResponse(url=request.url, body=body, encoding='utf-8', request=request)
            except Exception as e:
                spider.logger.error(f'Error processing request with Selenium: {e}')
                return None
        
        # For individual company pages, let Scrapy handle them normally (no Selenium)
        # This is much faster since company detail pages are mostly static HTML
        return None

    def spider_closed(self, spider):
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                spider.logger.error(f'Error closing driver: {e}')

