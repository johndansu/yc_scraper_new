# Define here the models for your spider middleware
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/spider-middleware.html

from scrapy import signals
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
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
        chrome_options.add_argument('--disable-images')  # Don't load images - faster
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-background-timer-throttling')
        chrome_options.add_argument('--disable-backgrounding-occluded-windows')
        chrome_options.add_argument('--disable-renderer-backgrounding')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        chrome_options.page_load_strategy = 'eager'  # Faster page loading - don't wait for full load
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(30)  # 30 second timeout for page loads
            self.driver.implicitly_wait(5)  # 5 second implicit wait
            print("✅ Selenium Chrome driver initialized successfully")
        except Exception as e:
            print(f"⚠️ Chrome driver failed: {e}")
            # If Chrome is not available, try Firefox
            try:
                from selenium.webdriver.firefox.options import Options as FirefoxOptions
                firefox_options = FirefoxOptions()
                firefox_options.add_argument('--headless')
                self.driver = webdriver.Firefox(options=firefox_options)
                print("✅ Selenium Firefox driver initialized successfully")
            except Exception as e2:
                print(f"❌ Error initializing browser drivers: {e}, {e2}")
                print("⚠️ Selenium will not be available - pages may not load correctly")
                self.driver = None

    @classmethod
    def from_crawler(cls, crawler):
        middleware = cls()
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        return middleware

    def process_request(self, request, spider):
        # Only use Selenium for the companies listing page (which has infinite scroll)
        # Skip Selenium for individual company pages - they're mostly static HTML
        is_listing_page = '/companies?' in request.url or '/companies' in request.url.split('?')[0].split('#')[0] or request.url.endswith('/companies')
        
        spider.logger.info(f'Selenium check: URL={request.url}, is_listing_page={is_listing_page}, has_driver={self.driver is not None}')
        
        if is_listing_page and 'ycombinator.com' in request.url and self.driver:
            spider.logger.info(f'Processing listing page {request.url} with Selenium')
            try:
                self.driver.set_page_load_timeout(30)  # 30 second timeout
                self.driver.get(request.url)
                
                # Wait for content to load (reduced from 1s)
                time.sleep(0.5)
                
                # Scroll to load more content (infinite scroll) - OPTIMIZED for speed
                spider.logger.info('Starting infinite scroll to load all companies...')
                last_height = self.driver.execute_script("return document.body.scrollHeight")
                scroll_attempts = 0
                max_scrolls = 50  # Reduced from 100 - more efficient stopping
                no_change_count = 0
                last_company_count = 0
                start_time = time.time()
                max_scroll_time = 120  # Max 2 minutes for scrolling
                
                while scroll_attempts < max_scrolls and (time.time() - start_time) < max_scroll_time:
                    # Scroll down
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(0.3)  # Reduced from 1.5s to 0.3s for faster scrolling
                    
                    # Check company count every 3 scrolls (not every scroll - saves time)
                    if scroll_attempts % 3 == 0:
                        try:
                            script = """
                            var links = document.querySelectorAll('a[href*="/companies/"]:not([href*="/companies?"])');
                            var hrefs = Array.from(links).map(l => l.href).filter(h => h && h.includes('/companies/') && !h.includes('companies?'));
                            return new Set(hrefs).size;
                            """
                            current_company_count = self.driver.execute_script(script)
                            
                            if current_company_count and current_company_count > last_company_count:
                                spider.logger.info(f'Loaded {current_company_count} companies so far...')
                                last_company_count = current_company_count
                                no_change_count = 0
                            else:
                                no_change_count += 1
                        except:
                            pass
                    
                    # Check scroll height
                    new_height = self.driver.execute_script("return document.body.scrollHeight")
                    if new_height == last_height:
                        no_change_count += 1
                        if no_change_count >= 3:  # Reduced from 5 to 3 - stop faster
                            spider.logger.info(f'No new content after {no_change_count} scrolls, stopping')
                            break
                    else:
                        no_change_count = 0
                        last_height = new_height
                    
                    scroll_attempts += 1
                
                spider.logger.info(f'Finished scrolling after {scroll_attempts} attempts ({int(time.time() - start_time)}s), found {last_company_count} companies')
                
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

