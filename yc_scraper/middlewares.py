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
        # ONLY use Playwright for the MAIN companies listing page (NOT individual company pages)
        is_main_listing = (
            request.url == 'https://www.ycombinator.com/companies' or 
            request.url.endswith('/companies') or
            '/companies?' in request.url or
            (request.url.endswith('/companies') and 'ycombinator.com' in request.url)
        )
        # Make sure we're NOT using Playwright for individual company pages
        is_company_page = '/companies/' in request.url and request.url != 'https://www.ycombinator.com/companies' and not request.url.endswith('/companies')
        
        if is_main_listing and not is_company_page and 'ycombinator.com' in request.url:
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
            
            # Navigate - try multiple wait strategies with fallback
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=10000)  # 10s timeout - faster
            except Exception as e:
                spider.logger.warning(f'domcontentloaded timed out, trying without wait: {e}')
                try:
                    await page.goto(url, timeout=10000)
                except:
                    pass  # Continue anyway
            
            # Wait for React app to load and companies to start appearing
            print("Waiting for companies to load...")
            await page.wait_for_timeout(3000)  # 3 seconds for React to initialize
            
            # Wait for at least some company links to appear
            try:
                await page.wait_for_function(
                    """
                    () => {
                        const links = Array.from(document.querySelectorAll('a[href*="/companies/"]'))
                            .filter(a => {
                                const href = a.getAttribute('href') || '';
                                return href.includes('/companies/') && 
                                       !href.includes('companies?') &&
                                       !href.match(/\\.(png|jpg|jpeg|gif|svg|webp|ico|css|js|json)$/i);
                            });
                        return links.length > 0;
                    }
                    """,
                    timeout=10000
                )
                print("✅ Companies started loading!")
            except:
                print("⚠️ Companies may not have loaded yet, continuing anyway...")
            
            # Now scroll aggressively to load ALL companies
            print("Scrolling to load ALL companies...")
            scroll_attempts = 0
            last_height = 0
            same_height_count = 0
            last_company_count = 0
            start_time = time.time()
            max_time = 60  # 60 seconds to load all companies (balance between speed and coverage)
            
            while (time.time() - start_time) < max_time:
                # Scroll to bottom
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                await page.wait_for_timeout(20)  # 20ms - need time for content to load
                
                # Check company count every 5 scrolls
                if scroll_attempts % 5 == 0:
                    try:
                        new_height = await page.evaluate("document.body.scrollHeight")
                        current_company_count = await page.evaluate("""
                            Array.from(document.querySelectorAll('a[href*="/companies/"]'))
                                .filter(a => {
                                    const href = a.getAttribute('href') || '';
                                    return href.includes('/companies/') && 
                                           !href.includes('companies?') &&
                                           !href.match(/\\.(png|jpg|jpeg|gif|svg|webp|ico|css|js|json)$/i);
                                }).length
                        """)
                        
                        # Show progress
                        if current_company_count and current_company_count > last_company_count:
                            if current_company_count % 100 == 0:
                                print(f'Loaded {current_company_count} companies so far...')
                            last_company_count = current_company_count
                        
                        # Stop if no height change for 5 checks
                        if new_height == last_height:
                            same_height_count += 1
                            if same_height_count >= 5:
                                # If we have 1000+ companies loaded, we might be done
                                if current_company_count >= 1000:  # If we have 1000+, likely done
                                    print(f'✅ Loaded {current_company_count} companies - likely all loaded')
                                    break
                        else:
                            same_height_count = 0
                            last_height = new_height
                    except:
                        pass
                
                scroll_attempts += 1
                if scroll_attempts > 500:
                    break
            
            print(f'✅ Scrolling complete: {scroll_attempts} scrolls in {int(time.time() - start_time)}s')
            
            # Get final company count - exclude images and files
            try:
                final_count = await page.evaluate("""
                    Array.from(document.querySelectorAll('a[href*="/companies/"]'))
                        .filter(a => {
                            const href = a.getAttribute('href') || '';
                            return href.includes('/companies/') && 
                                   !href.includes('companies?') &&
                                   !href.match(/\\.(png|jpg|jpeg|gif|svg|webp|ico|css|js|json)$/i);
                        }).length
                """)
                print(f'✅ Finished scrolling: Found {final_count} company links in page')
            except:
                pass
            
            print('✅ Playwright: Finished scrolling - page loaded')
            
            # Try to find companies via JavaScript BEFORE getting page content
            company_links_js = []
            try:
                # Use JavaScript to find all company links in the DOM
                company_links_js = await page.evaluate("""
                    () => {
                        const links = [];
                        // Find all links with /companies/ in href
                        document.querySelectorAll('a[href*="/companies/"]').forEach(a => {
                            const href = a.getAttribute('href') || '';
                            // Exclude query params, images, and other files
                            if (href.includes('/companies/') && 
                                !href.includes('companies?') && 
                                !href.match(/\\.(png|jpg|jpeg|gif|svg|webp|ico|css|js|json)$/i) &&
                                !href.endsWith('.png') &&
                                href.split('/companies/')[1] && 
                                href.split('/companies/')[1].length > 0) {
                                links.push(href);
                            }
                        });
                        return [...new Set(links)]; // Remove duplicates
                    }
                """)
                if company_links_js:
                    spider.logger.info(f'✅ Found {len(company_links_js)} company links via JavaScript DOM query')
                    print(f'✅ Found {len(company_links_js)} company links via JavaScript DOM query')
                    for link in company_links_js[:5]:
                        spider.logger.info(f'  - {link}')
                        print(f'  - {link}')
            except Exception as e:
                spider.logger.warning(f'Could not query company links via JS: {e}')
            
            # Get page content
            body = await page.content()
            await page.close()
            
            # Save HTML for debugging if no companies found
            if not company_links_js and len(body) > 1000:
                try:
                    debug_file = 'debug_page_source.html'
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        f.write(body)
                    spider.logger.info(f'💾 Saved page HTML to {debug_file} for debugging')
                    print(f'💾 Saved page HTML to {debug_file} for debugging')
                except:
                    pass
            
            # Check if page has content
            if len(body) < 1000:
                spider.logger.warning(f'Page source is very short ({len(body)} chars) - may not have loaded')
            else:
                import re
                # Find company links but exclude image files
                all_links = re.findall(r'/companies/[^"\'<>?\s]+', body)
                # Filter out image files and other non-company URLs
                excluded_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico', '.css', '.js', '.json']
                company_links = [link for link in all_links if not any(link.lower().endswith(ext) for ext in excluded_extensions)]
                company_link_count = len(company_links)
                
                spider.logger.info(f'Found {company_link_count} company links in page source (filtered from {len(all_links)} total)')
                print(f'Found {company_link_count} company links in page source (filtered from {len(all_links)} total)')
                
                # If we found links via JS but not in HTML, log it
                if company_links_js and not company_links:
                    spider.logger.warning('⚠️ Found companies via JavaScript but not in HTML - page might use dynamic loading')
                    print('⚠️ Found companies via JavaScript but not in HTML - page might use dynamic loading')
            
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
