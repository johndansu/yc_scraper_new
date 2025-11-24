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
        
        # Extract company website
        # Look for external links that are not YC links
        all_links = response.css('a[href^="http"]::attr(href)').getall()
        company_website = ''
        for link in all_links:
            if 'ycombinator.com' not in link and 'linkedin.com' not in link and 'twitter.com' not in link and 'x.com' not in link:
                company_website = link
                break
        
        if not company_website:
            # Try specific selectors
            company_website = (
                response.css('a[href^="http"]:not([href*="ycombinator"]):not([href*="linkedin"]):not([href*="twitter"]):not([href*="x.com"])::attr(href)').get() or
                response.css('[data-website]::attr(data-website)').get() or
                response.css('.website a::attr(href), a.website::attr(href)').get()
            )
        
        item['company_website'] = company_website.strip() if company_website else ''
        
        # Extract founder information
        founders_names = []
        founders_linkedin = []
        founders_twitter = []
        
        # Try to find founder sections - YC typically has founder info in specific sections
        founder_sections = response.css('[class*="founder"], [class*="Founder"], [data-founder], .founders, .founder')
        
        for founder_section in founder_sections:
            # Extract founder name
            founder_name = (
                founder_section.css('h3::text, h4::text, h5::text').get() or
                founder_section.css('[class*="name"]::text, [class*="Name"]::text').get() or
                founder_section.css('strong::text, b::text').get()
            )
            if founder_name and founder_name.strip():
                founders_names.append(founder_name.strip())
            
            # Extract LinkedIn
            linkedin = founder_section.css('a[href*="linkedin.com/in/"]::attr(href)').get()
            if linkedin:
                founders_linkedin.append(linkedin)
            
            # Extract Twitter
            twitter = founder_section.css('a[href*="twitter.com/"], a[href*="x.com/"]::attr(href)').get()
            if twitter:
                founders_twitter.append(twitter)
        
        # If no founder sections found, try to extract from anywhere on page
        if not founders_names:
            # Look for LinkedIn profiles - often founder profiles
            linkedin_links = response.css('a[href*="linkedin.com/in/"]::attr(href)').getall()
            if linkedin_links:
                founders_linkedin = list(set(linkedin_links))
                # Try to get names from near LinkedIn links
                for link in linkedin_links[:3]:  # Limit to first 3
                    # Find parent element and extract name
                    parent = response.css(f'a[href="{link}"]').xpath('..')
                    name = parent.css('::text').get()
                    if name and name.strip():
                        founders_names.append(name.strip())
        
        # Extract Twitter links
        if not founders_twitter:
            twitter_links = response.css('a[href*="twitter.com/"], a[href*="x.com/"]::attr(href)').getall()
            founders_twitter = list(set(twitter_links))
        
        # Set item fields
        item['founders_name'] = ', '.join(set(founders_names)) if founders_names else ''
        item['founders_linkedin'] = ', '.join(set(founders_linkedin)) if founders_linkedin else ''
        item['founders_twitter'] = ', '.join(set(founders_twitter)) if founders_twitter else ''
        
        # Only yield if we have at least a company name
        if item.get('company_name'):
            yield item
        else:
            self.logger.warning(f'No company name found for {response.url}')

