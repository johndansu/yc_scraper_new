import scrapy
from yc_scraper.items import YcCompanyItem
import re


class YcCompaniesSpider(scrapy.Spider):
    name = 'yc_companies'
    allowed_domains = ['ycombinator.com']
    
    start_urls = [
        'https://www.ycombinator.com/companies?batch=Fall%202024&batch=Winter%202024&batch=Summer%202024&batch=Winter%202025&batch=Spring%202025&batch=Summer%202025&batch=Fall%202025&batch=Winter%202026'
    ]

    def parse(self, response):
        """Parse the Y Combinator companies page"""
        self.logger.info(f'Parsing page: {response.url}')
        
        # Y Combinator uses specific structure - try multiple selectors
        # Common patterns: links to /companies/, divs with company info
        company_links = response.css('a[href*="/companies/"]:not([href*="/companies?"])')
        
        # Also try to find company cards/items
        company_cards = response.css('[class*="CompanyCard"], [class*="company-card"], [data-testid*="company"]')
        
        # Combine both approaches
        all_companies = list(company_links) + list(company_cards)
        
        if not all_companies:
            # Fallback: try to find any link containing company info
            all_companies = response.css('a[href*="companies"]')
        
        self.logger.info(f'Found {len(all_companies)} potential company links')
        
        processed_urls = set()
        
        for element in all_companies:
            # Get company detail page URL
            company_link = element.css('::attr(href)').get()
            if not company_link:
                continue
                
            if '/companies/' in company_link and company_link not in processed_urls:
                full_url = response.urljoin(company_link)
                processed_urls.add(company_link)
                
                # Extract basic info from listing if available
                company_name = (
                    element.css('h3::text, h2::text, h4::text').get() or
                    element.css('[class*="name"]::text, [class*="Name"]::text').get() or
                    element.css('::text').get()
                )
                
                item = YcCompanyItem()
                if company_name:
                    item['company_name'] = company_name.strip()
                
                # Follow link to get full details
                yield scrapy.Request(
                    full_url,
                    callback=self.parse_company_detail,
                    meta={'item': item}
                )

    def parse_company_detail(self, response):
        """Parse individual company detail page for more information"""
        item = response.meta.get('item', YcCompanyItem())
        
        # Extract company name if not already set
        if not item.get('company_name'):
            company_name = (
                response.css('h1::text, h2::text, [class*="company-name"]::text, [class*="CompanyName"]::text').get() or
                response.css('title::text').get()
            )
            if company_name:
                item['company_name'] = company_name.strip().replace(' | Y Combinator', '').strip()
        
        # Extract company website - look for the actual company website link
        # Exclude YC, social media, and other common non-company links
        excluded_domains = [
            'ycombinator.com', 'linkedin.com', 'twitter.com', 'x.com', 
            'startupschool.org', 'bookface-static.ycombinator.com',
            'bookface-images.s3', 'facebook.com', 'instagram.com',
            'youtube.com', 'google.com', 'maps.googleapis.com'
        ]
        
        company_website = ''
        
        # Try to find website link near company name/section
        # Look for links that are clearly the company's main website
        website_selectors = [
            'a[href^="http"]:not([href*="ycombinator"]):not([href*="linkedin"]):not([href*="twitter"]):not([href*="x.com"]):not([href*="startupschool"]):not([href*="bookface"]):not([href*="facebook"]):not([href*="instagram"]):not([href*="youtube"]):not([href*="maps"])::attr(href)',
            '[data-website]::attr(data-website)',
            '.website a::attr(href)',
            'a.website::attr(href)',
            'a[href*="http"]:not([href*="ycombinator"]):not([href*="linkedin"]):not([href*="twitter"]):not([href*="x.com"]):not([href*="startupschool"]):not([href*="bookface"])::attr(href)'
        ]
        
        for selector in website_selectors:
            links = response.css(selector).getall()
            for link in links:
                if link and link.startswith('http'):
                    # Check if it's not in excluded domains
                    is_excluded = any(domain in link.lower() for domain in excluded_domains)
                    if not is_excluded:
                        company_website = link
                        break
            if company_website:
                break
        
        item['company_website'] = company_website.strip() if company_website else ''
        
        # Extract founder information - improved extraction
        founders_names = []
        founders_linkedin = []
        founders_twitter = []
        
        # Find "Active Founders" section using XPath
        founder_sections_xpath = response.xpath('//section[.//text()[contains(., "Active Founders") or contains(., "Founder")]]')
        if not founder_sections_xpath:
            # Fallback: try CSS selectors
            founder_sections = response.css('[class*="founder"], [class*="Founder"], [data-founder], .founders, .founder')
        else:
            # Convert XPath results to SelectorList for processing
            founder_sections = founder_sections_xpath
        
        found_founders = False
        
        # Process founder sections
        for founder_section in founder_sections[:5]:  # Limit to first 5
            # Extract founder name - try multiple approaches
            name_candidates = []
            
            # Try headings first
            headings = founder_section.css('h1::text, h2::text, h3::text, h4::text, h5::text').getall()
            for heading in headings:
                if heading and heading.strip():
                    name_candidates.append(heading.strip())
            
            # Try text in divs with name-like classes
            name_texts = founder_section.css('div[class*="name"]::text, div[class*="Name"]::text, span[class*="name"]::text').getall()
            for text in name_texts:
                if text and text.strip() and len(text.strip()) > 2:
                    name_candidates.append(text.strip())
            
            # If we have name candidates, clean and add them
            for name_text in name_candidates:
                name_clean = name_text.strip()
                # Remove "Founder", "Co-founder", etc. if it's in the text
                name_clean = re.sub(r'\b(Co-?)?Founder\b', '', name_clean, flags=re.IGNORECASE).strip()
                # Remove extra whitespace and separators
                name_clean = re.sub(r'[|\-–—]', '', name_clean).strip()
                
                # Only add if it looks like a name
                if len(name_clean) > 2 and name_clean:
                    # Check if it's not a URL, social media handle, or common text
                    if not any(x in name_clean.lower() for x in ['http', '.com', '@', 'linkedin', 'twitter', '|', 'active founder', 'founders']):
                        if name_clean not in founders_names:
                            founders_names.append(name_clean)
            
            # Extract LinkedIn
            linkedin_links = founder_section.css('a[href*="linkedin.com/in/"]::attr(href)').getall()
            for linkedin in linkedin_links:
                if linkedin and linkedin not in founders_linkedin:
                    founders_linkedin.append(linkedin)
            
            # Extract Twitter - but exclude @ycombinator
            twitter_links = founder_section.css('a[href*="twitter.com/"], a[href*="x.com/"]::attr(href)').getall()
            for twitter in twitter_links:
                if twitter and 'ycombinator' not in twitter.lower():
                    if twitter not in founders_twitter:
                        founders_twitter.append(twitter)
            
            if founders_names or founders_linkedin:
                found_founders = True
        
        # If we didn't find founders in sections, try alternative approach
        if not found_founders:
            # Look for LinkedIn profiles and extract names from nearby elements
            linkedin_links = response.css('a[href*="linkedin.com/in/"]::attr(href)').getall()
            for linkedin_url in linkedin_links[:5]:  # Limit to 5
                if linkedin_url and linkedin_url not in founders_linkedin:
                    founders_linkedin.append(linkedin_url)
                    
                    # Try to find name near this LinkedIn link using XPath
                    # Find the link element and then look for text in parent/ancestor
                    xpath_query = f'//a[@href="{linkedin_url}"]/ancestor::*[position()<=3]//text()[normalize-space()][not(ancestor::a)]'
                    nearby_texts = response.xpath(xpath_query).getall()
                    
                    for text in nearby_texts[:5]:  # Check first few text elements
                        if text:
                            text_clean = text.strip()
                            # Check if it looks like a name (has reasonable length and no URLs)
                            if (len(text_clean) > 2 and len(text_clean) < 50 and 
                                not any(x in text_clean.lower() for x in ['http', '.com', '@', 'linkedin', 'twitter', 'founder', '|', 'view', 'profile']) and
                                text_clean not in founders_names):
                                # Check if it has at least one word (likely a name)
                                if len(text_clean.split()) >= 1:
                                    founders_names.append(text_clean)
                                    break
            
            # Extract Twitter links (excluding @ycombinator)
            twitter_links = response.css('a[href*="twitter.com/"], a[href*="x.com/"]::attr(href)').getall()
            for twitter_url in twitter_links:
                if twitter_url and 'ycombinator' not in twitter_url.lower():
                    if twitter_url not in founders_twitter:
                        founders_twitter.append(twitter_url)
        
        # Final cleanup - remove @ycombinator from Twitter if somehow included
        founders_twitter = [t for t in founders_twitter if 'ycombinator' not in t.lower()]
        
        # Set item fields
        item['founders_name'] = ', '.join(set(founders_names)) if founders_names else ''
        item['founders_linkedin'] = ', '.join(set(founders_linkedin)) if founders_linkedin else ''
        item['founders_twitter'] = ', '.join(set(founders_twitter)) if founders_twitter else ''
        
        # Only yield if we have at least a company name
        if item.get('company_name'):
            yield item
        else:
            self.logger.warning(f'No company name found for {response.url}')

