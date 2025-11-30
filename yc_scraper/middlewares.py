# Define here the models for your spider middleware
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/spider-middleware.html

from scrapy import signals
from scrapy.http import HtmlResponse
from playwright.async_api import async_playwright
import asyncio
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

    def process_spider_exception(self, response, exception):
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


class PlaywrightMiddleware:
    """Middleware to handle JavaScript-rendered pages using Playwright Async API - FAST!"""

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self._initialized = False
        self._loop = None

    @classmethod
    def from_crawler(cls, crawler):
        middleware = cls()
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        return middleware
    
    def _get_event_loop(self):
        """Get or create event loop for async operations"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop
    
    def _initialize_playwright(self):
        """Initialize Playwright using async API - lazy initialization"""
        if self._initialized:
            return True
        
        try:
            print("Initializing Playwright (async)...")
            
            # Get event loop
            self._loop = self._get_event_loop()
            
            # Run async initialization
            result = self._loop.run_until_complete(self._async_init_playwright())
            
            if result:
                self._initialized = True
                print("✅ Playwright browser initialized successfully - FAST!")
                return True
            else:
                return False
        except Exception as e:
            print(f"❌ Error initializing Playwright: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def _async_init_playwright(self):
        """Async initialization of Playwright"""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-images',
                    '--disable-plugins',
                    '--disable-extensions',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                ]
            )
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                java_script_enabled=True,
            )
            return True
        except Exception as e:
            print(f"❌ Error in async Playwright init: {e}")
            return False

    def process_request(self, request, spider):
        """Process request with Playwright for JavaScript pages"""
        # Only use Playwright for the companies listing page (which has infinite scroll)
        is_listing_page = '/companies?' in request.url or '/companies' in request.url.split('?')[0].split('#')[0] or request.url.endswith('/companies')
        
        if is_listing_page and 'ycombinator.com' in request.url:
            # Lazy initialize Playwright only when needed
            if not self._initialized:
                if not self._initialize_playwright():
                    spider.logger.error('Playwright failed to initialize - JavaScript pages may not load')
                    return None
            
            if not self.context:
                return None
            
            spider.logger.info(f'Processing listing page {request.url} with Playwright (FAST)')
            try:
                print(f'Loading URL with Playwright: {request.url}')
                
                # Run async page processing
                self._loop = self._loop or self._get_event_loop()
                body = self._loop.run_until_complete(self._async_process_page(request.url, spider))
                
                if body:
                    return HtmlResponse(url=request.url, body=body.encode('utf-8'), encoding='utf-8', request=request)
                else:
                    return None
            except Exception as e:
                spider.logger.error(f'Error processing request with Playwright: {e}')
                import traceback
                traceback.print_exc()
                return None
        
        # For individual company pages, let Scrapy handle them normally
        return None
    
    async def _async_process_page(self, url, spider):
        """Async page processing with Playwright"""
        try:
            # Create a new page for this request
            page = await self.context.new_page()
            
            # Navigate - FAST
            await page.goto(url, wait_until='domcontentloaded', timeout=20000)
            await page.wait_for_timeout(200)  # 200ms for initial load
            
            # AGGRESSIVE scrolling to load ALL companies - ensure we get everything
            print("Scrolling to load all companies...")
            scroll_attempts = 0
            last_height = 0
            same_height_count = 0
            last_company_count = 0
            start_time = time.time()
            max_time = 45  # 45 seconds to ensure all companies load
            
            while (time.time() - start_time) < max_time:
                # Scroll to bottom
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                await page.wait_for_timeout(50)  # 50ms - need time for content to load
                
                # Check company count and height every 5 scrolls
                if scroll_attempts % 5 == 0:
                    try:
                        new_height = await page.evaluate("document.body.scrollHeight")
                        current_company_count = await page.evaluate(
                            "document.querySelectorAll('a[href*=\"/companies/\"]:not([href*=\"/companies?\"])').length"
                        )
                        
                        if new_height == last_height:
                            same_height_count += 1
                            if same_height_count >= 8:  # Need more consistency
                                # Double-check company count hasn't changed
                                if current_company_count == last_company_count:
                                    break
                        else:
                            same_height_count = 0
                            last_height = new_height
                        
                        if current_company_count and current_company_count > last_company_count:
                            print(f'Loaded {current_company_count} companies so far...')
                            last_company_count = current_company_count
                    except:
                        pass
                
                scroll_attempts += 1
                
                # Safety limit
                if scroll_attempts > 300:
                    break
            
            # Extra scrolls to ensure everything loaded
            print("Final scrolls to ensure all companies loaded...")
            for _ in range(20):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                await page.wait_for_timeout(30)
            
            # Get final company count
            try:
                final_count = await page.evaluate(
                    "document.querySelectorAll('a[href*=\"/companies/\"]:not([href*=\"/companies?\"])').length"
                )
                print(f'✅ Finished scrolling: Found {final_count} company links in page')
            except:
                pass
            
            print('✅ Playwright: Finished scrolling - page loaded')
            
            # Get page content
            body = await page.content()
            await page.close()
            
            # Check if page has content
            if len(body) < 1000:
                spider.logger.warning(f'Page source is very short ({len(body)} chars) - may not have loaded')
            else:
                import re
                company_link_count = len(re.findall(r'/companies/[^"\'<>?\s]+', body))
                spider.logger.info(f'Found {company_link_count} company links in page source')
                print(f'Found {company_link_count} company links in page source')
            
            return body
        except Exception as e:
            spider.logger.error(f'Error in async page processing: {e}')
            import traceback
            traceback.print_exc()
            return None

    def spider_closed(self, spider):
        """Clean up Playwright resources"""
        try:
            if self._initialized and self._loop:
                # Clean up async resources
                self._loop.run_until_complete(self._async_cleanup())
            print("✅ Playwright browser closed successfully")
        except Exception as e:
            spider.logger.error(f'Error closing Playwright: {e}')
    
    async def _async_cleanup(self):
        """Async cleanup of Playwright resources"""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            print(f"Error in async cleanup: {e}")
