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
        
        # Extract founder information - Names are bold/larger text above "Founder"
        founders_names = []
        founders_linkedin = []
        founders_twitter = []
        
        # Find the "Active Founders" section
        active_founders_section = response.xpath('//section[.//text()[contains(., "Active Founders")]] | //div[.//text()[contains(., "Active Founders")]]')
        
        if not active_founders_section:
            # Fallback: look for any section with founder content
            active_founders_section = response.xpath('//section | //div').css('[class*="founder"]')
        
        if active_founders_section:
            founders_section = active_founders_section[0]
        else:
            founders_section = response
        
        # Strategy: Find text nodes that exactly say "Founder" (not "Founders") 
        # and get the heading/text element that appears immediately before it
        # The name is the bold/larger heading above "Founder"
        
        # Find all text nodes containing exactly "Founder"
        founder_text_nodes = founders_section.xpath('.//text()[normalize-space()="Founder"]')
        
        processed_containers = set()
        
        for founder_text in founder_text_nodes[:10]:  # Limit to 10
            # Get the element containing "Founder" text
            founder_elem = founder_text.xpath('./parent::*')
            
            if not founder_elem:
                continue
            
            # Get the container/block this founder belongs to
            container = founder_elem[0].xpath('./ancestor::div[position()<=5][1] | ./ancestor::section[position()<=3][1]')
            
            if not container:
                continue
            
            container_id = str(container[0].extract())[:100]  # Create ID to avoid duplicates
            if container_id in processed_containers:
                continue
            processed_containers.add(container_id)
            
            container_elem = container[0]
            
            # Look for the name - it should be a heading BEFORE the "Founder" element
            # Try multiple methods to find the name heading
            
            # Method 1: Look for preceding sibling headings
            name = founder_elem[0].xpath('./preceding-sibling::h1[1]/text() | ./preceding-sibling::h2[1]/text() | ./preceding-sibling::h3[1]/text() | ./preceding-sibling::h4[1]/text() | ./preceding-sibling::h5[1]/text()').get()
            
            # Method 2: Look for headings in the container before "Founder" element
            if not name:
                # Get all headings in container, find the one before "Founder"
                all_headings = container_elem.xpath('.//h1 | .//h2 | .//h3 | .//h4 | .//h5')
                founder_pos = None
                for idx, heading in enumerate(all_headings):
                    # Check if "Founder" comes after this heading
                    if founder_elem[0].xpath('count(./preceding::*)') > heading.xpath('count(./preceding::*)'):
                        founder_pos = idx
                        break
                if founder_pos and founder_pos > 0:
                    name = all_headings[founder_pos - 1].xpath('./text()').get()
            
            # Method 3: Get first heading in the container (usually the name)
            if not name:
                name = container_elem.xpath('.//h1[1]/text() | .//h2[1]/text() | .//h3[1]/text() | .//h4[1]/text() | .//h5[1]/text()').get()
            
            # Method 4: Look for bold/strong text before "Founder"
            if not name:
                name = founder_elem[0].xpath('./preceding-sibling::strong[1]/text() | ./preceding-sibling::b[1]/text() | ./preceding::strong[1]/text() | ./preceding::b[1]/text()').get()
            
            if name:
                name_clean = name.strip()
                # Clean up - remove "Founder" if somehow included
                name_clean = re.sub(r'\b(Co-?)?Founder\b', '', name_clean, flags=re.IGNORECASE).strip()
                
                # Validation - must look like a name
                if (name_clean and 
                    2 <= len(name_clean) <= 50 and
                    name_clean.lower() not in ['active', 'founders', 'founder'] and
                    'http' not in name_clean.lower() and
                    not name_clean.endswith('.') and
                    not any(word in name_clean.lower() for word in ['based', 'located', 'company']) and
                    name_clean not in founders_names):
                    founders_names.append(name_clean)
            
            # Get LinkedIn and Twitter from this container
            linkedin = container_elem.css('a[href*="linkedin.com/in/"]::attr(href)').get()
            if linkedin and linkedin not in founders_linkedin:
                founders_linkedin.append(linkedin)
            
            twitter = container_elem.css('a[href*="twitter.com/"], a[href*="x.com/"]::attr(href)').get()
            if twitter and 'ycombinator' not in twitter.lower() and twitter not in founders_twitter:
                founders_twitter.append(twitter)
        
        # Alternative approach: Find each LinkedIn link and get the heading before "Founder" text in same container
        if not founders_names:
            linkedin_links = founders_section.css('a[href*="linkedin.com/in/"]::attr(href)').getall()
            for linkedin_url in linkedin_links[:10]:
                if linkedin_url and linkedin_url not in founders_linkedin:
                    founders_linkedin.append(linkedin_url)
                    
                    # Find the LinkedIn link element
                    link_elem = founders_section.xpath(f'.//a[@href="{linkedin_url}"]')
                    if link_elem:
                        # Get parent container
                        container = link_elem[0].xpath('./ancestor::div[position()<=4][1] | ./ancestor::section[position()<=3][1]')
                        if container:
                            # Look for heading in this container
                            name = container[0].xpath('.//h3[1]/text() | .//h4[1]/text() | .//h2[1]/text() | .//h1[1]/text()').get()
                            if name and name.strip():
                                name_clean = name.strip()
                                if (2 <= len(name_clean) <= 50 and
                                    'founder' not in name_clean.lower() and
                                    'active' not in name_clean.lower() and
                                    name_clean not in founders_names):
                                    founders_names.append(name_clean)
                            
                            twitter = container[0].css('a[href*="twitter.com/"], a[href*="x.com/"]::attr(href)').get()
                            if twitter and 'ycombinator' not in twitter.lower() and twitter not in founders_twitter:
                                founders_twitter.append(twitter)
        
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

