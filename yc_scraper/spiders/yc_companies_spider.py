import scrapy
from yc_scraper.items import YcCompanyItem
import re
import os
from datetime import datetime
import io


class YcCompaniesSpider(scrapy.Spider):
    name = 'yc_companies'
    allowed_domains = ['ycombinator.com']
    
    start_urls = [
        # Start with base companies page - we'll filter by year on individual pages
        'https://www.ycombinator.com/companies'
    ]
    
    def __init__(self, *args, **kwargs):
        super(YcCompaniesSpider, self).__init__(*args, **kwargs)
        self.processed_count = 0
        self.skipped_count = 0
        # Skip debug logging for speed - only log errors
        self.enable_debug = False  # Disable debug logging for maximum speed
    
    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(YcCompaniesSpider, cls).from_crawler(crawler, *args, **kwargs)
        return spider
    
    def _write_debug(self, message):
        """Helper method to write to debug log - disabled for speed"""
        if not getattr(self, 'enable_debug', False):
            return  # Skip debug logging for maximum speed
        # Only log critical errors, not regular processing
    
    def closed(self, reason):
        """Called when spider closes"""
        print(f"\n=== Scraping Complete ===")
        print(f"Processed: {getattr(self, 'processed_count', 0)} companies (2024+)")
        print(f"Skipped: {getattr(self, 'skipped_count', 0)} companies (pre-2024)")

    def _is_valid_name(self, text, existing_names):
        """Validate if extracted text is a plausible founder name"""
        if not text or not isinstance(text, str):
            return False
        text = text.strip()
        if len(text) < 2 or len(text) > 80:
            return False
        
        # Exclude common non-name words
        exclude_words = ['founder', 'founders', 'active founders', 'co-founder', 'co-founders',
                        'linkedin', 'twitter', 'http', 'https', 'www', 'ycombinator',
                        'based', 'located', 'company', 'website', 'email', 'contact',
                        'click', 'here', 'more', 'read', 'view', 'profile',
                        'tl;dr', 'our ask', 'our story', 'why we', 'problem', 'solution',
                        'the knowledge', 'we are working']
        text_lower = text.lower()
        if any(word in text_lower for word in exclude_words):
            return False
        if 'http' in text_lower or text_lower.startswith('www.') or '@' in text:
            return False
        if text in existing_names:
            return False
        
        words = text.split()
        word_count = len(words)
        # Allow single word names if they're at least 4 chars (some people have single names)
        if word_count < 1 or word_count > 5:
            return False
        if word_count == 1 and len(words[0]) < 3:
            return False
        
        # Must have at least one capital letter (proper name)
        has_capital = any(any(c.isupper() for c in word) for word in words)
        if not has_capital:
            return False
        
        # First word should start with capital
        if words and not words[0][0].isupper():
            return False
        
        # Filter out names that are clearly IDs or usernames (all lowercase with numbers)
        if word_count == 1 and words[0].islower() and any(c.isdigit() for c in words[0]):
            # Single lowercase word with numbers is likely a username, not a name
            if len([c for c in words[0] if c.isdigit()]) >= 2:
                return False
        
        # Exclude common words that aren't names
        common_words = ['the', 'and', 'or', 'but', 'for', 'with', 'from', 'about']
        if all(word.lower() in common_words for word in words):
            return False
        
        # Must contain at least one letter
        if not any(c.isalpha() for c in text):
            return False
        
        return True

    def _extract_batch_from_listing_card(self, element):
        """Try to extract batch/year info from a company card on the listing page - FAST"""
        # Get minimal text for speed
        card_text = ' '.join(element.css('::text').getall())
        card_text = ' '.join(card_text.split())  # Normalize whitespace
        
        # Look for batch patterns - prioritize 2024+ patterns first
        batch_patterns = [
            r'(W|S)(2[4-9]|[3-9][0-9])',  # W24, S24, W25, etc.
            r'20(2[4-9]|[3-9][0-9])',  # 2024, 2025, etc. (check years first)
            r'(Winter|Summer|Fall|Spring)\s+20(2[4-9]|[3-9][0-9])',  # Winter 2024, etc.
        ]
        
        for pattern in batch_patterns:
            match = re.search(pattern, card_text, re.IGNORECASE)
            if match:
                batch = match.group(0).upper()
                # Quick check - if it's clearly pre-2024, return early
                if re.search(r'(W|S)(1[0-9]|2[0-3])', batch) or re.search(r'20(1[0-9]|2[0-3])', batch):
                    return 'PRE_2024'  # Signal it's pre-2024
                # Check if it's 2024+
                if re.search(r'(W|S)(2[4-9]|[3-9][0-9])', batch) or re.search(r'20(2[4-9]|[3-9][0-9])', batch):
                    return batch
        return None
    
    def parse(self, response):
        """Parse the Y Combinator companies page - FAST with 2024+ filtering"""
        self.logger.info(f'Parsing page: {response.url}')
        print(f'Parsing companies listing page...')
        
        # Try multiple selector strategies - the page structure may vary
        all_companies = []
        seen_urls = set()
        
        # Strategy 1: CSS selector - FAST
        company_links = response.css('a[href*="/companies/"]')
        
        for element in company_links:
            href = element.css('::attr(href)').get() or ''
            if href and '/companies/' in href and 'companies?' not in href:
                parts = href.split('/companies/')
                if len(parts) > 1:
                    company_slug = parts[-1].split('?')[0].split('#')[0].strip()
                    if company_slug and company_slug not in seen_urls and company_slug != 'companies':
                        seen_urls.add(company_slug)
                        all_companies.append(element)
        
        # Strategy 2: XPath fallback if CSS didn't work
        if not all_companies:
            xpath_links = response.xpath('//a[contains(@href, "/companies/") and not(contains(@href, "companies?"))]')
            for element in xpath_links:
                href = element.xpath('./@href').get() or ''
                if href:
                    parts = href.split('/companies/')
                    if len(parts) > 1:
                        company_slug = parts[-1].split('?')[0].split('#')[0].strip()
                        if company_slug and company_slug not in seen_urls and company_slug != 'companies':
                            seen_urls.add(company_slug)
                            all_companies.append(element)
        
        # Strategy 3: Regex fallback - extract from HTML directly (ALWAYS use this - most reliable)
        html_text = response.text
        # Find all /companies/ URLs in the HTML - more comprehensive pattern
        company_urls = re.findall(r'["\']([^"\']*\/companies\/[^"\'\?\s&<>]+)', html_text)
        # Also try without quotes
        company_urls2 = re.findall(r'href=["\']?([^"\'\s<>]*\/companies\/[^"\'\?\s&<>]+)', html_text, re.IGNORECASE)
        company_urls.extend(company_urls2)
        
        for url in company_urls:
            if 'companies?' not in url and '/companies/' in url:
                parts = url.split('/companies/')
                if len(parts) > 1:
                    company_slug = parts[-1].split('?')[0].split('#')[0].strip()
                    # Filter out invalid slugs
                    if company_slug and company_slug not in seen_urls and company_slug != 'companies' and len(company_slug) > 1:
                        seen_urls.add(company_slug)
                        # Create a mock element dict for consistency
                        full_url = response.urljoin(url if url.startswith('http') else f'/companies/{company_slug}')
                        all_companies.append({'href': url, 'url': full_url})
        
        print(f'✅ Found {len(all_companies)} total company links - filtering to 2024+ only...')
        
        processed_urls = set()
        company_count = 0
        filtered_count = 0
        
        for element in all_companies:
            # Get company detail page URL - handle both Selector objects and dicts
            if isinstance(element, dict):
                company_link = element.get('url') or element.get('href')
            else:
                company_link = element.css('::attr(href)').get() or element.xpath('./@href').get()
            
            if not company_link:
                continue
            
            if not company_link.startswith('http'):
                company_link = response.urljoin(company_link)
                
            if '/companies/' in company_link and company_link not in processed_urls:
                # Extract batch from card - FAST filter (skip for dict elements)
                batch_from_card = None
                if not isinstance(element, dict):
                    batch_from_card = self._extract_batch_from_listing_card(element)
                
                # STRICT 2024+ FILTERING: Skip immediately if pre-2024
                if batch_from_card == 'PRE_2024':
                    filtered_count += 1
                    continue
                
                # If we have batch info and it's 2024+, proceed
                # If no batch info, we'll check on detail page
                full_url = response.urljoin(company_link)
                processed_urls.add(company_link)
                
                company_count += 1
                if company_count % 50 == 0:
                    print(f'Queued {company_count} companies for processing (filtered {filtered_count} pre-2024)...')
                
                item = YcCompanyItem()
                yield scrapy.Request(
                    full_url,
                    callback=self.parse_company_detail,
                    meta={'item': item, 'batch_from_card': batch_from_card},
                    dont_filter=False,
                    priority=1 if batch_from_card and batch_from_card != 'PRE_2024' else 0
                )
        
        print(f'Total: {company_count} companies queued, {filtered_count} filtered out on listing page')

    def _extract_batch_year(self, response):
        """Extract the batch/year information from the company page - FAST"""
        # FAST: Check page text first (regex is faster than CSS)
        page_text = response.text[:50000]  # Only check first 50k chars for speed
        
        # Look for batch patterns - prioritize 2024+ patterns first
        batch_patterns = [
            r'(W|S)(2[4-9]|[3-9][0-9])',  # W24, S24, W25, etc. (2024+ first)
            r'20(2[4-9]|[3-9][0-9])',  # Years 2024-2099
            r'(W|S)(1[0-9]|2[0-3])',  # Pre-2024 batches (for rejection)
            r'20(0[0-9]|1[0-9]|2[0-3])',  # Pre-2024 years (for rejection)
        ]
        
        for pattern in batch_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                return match.group(0).upper()
        
        # Fallback: Try CSS selectors (slower, but more thorough)
        batch_selectors = [
            '[class*="batch"]::text',
            '[data-batch]::attr(data-batch)',
        ]
        
        for selector in batch_selectors[:2]:  # Only try first 2 for speed
            try:
                batch_elements = response.css(selector).getall()
                for elem in batch_elements[:1]:  # Only check first match
                    if elem:
                        return elem.strip().upper()
            except:
                continue
        
        return ''
    
    def _is_2024_or_later(self, batch_text):
        """Check if the batch is from 2024 or later - LENIENT for 2024+"""
        if not batch_text:
            return True  # LENIENT: If we can't determine, include it (better to over-include)
        
        batch_text = batch_text.upper()
        
        # Check for explicit pre-2024 years first (faster rejection)
        if re.search(r'20(0[0-9]|1[0-9]|2[0-3])', batch_text):
            return False
        
        # Check for pre-2024 batch codes
        if re.search(r'(W|S)(0[0-9]|1[0-9]|2[0-3])', batch_text):
            return False
        
        # Check for explicit 2024+ years
        year_match = re.search(r'20(2[4-9]|[3-9][0-9])', batch_text)
        if year_match:
            year = int(year_match.group(0))
            return year >= 2024
        
        # Check for 2024+ batch codes (W24 = Winter 2024, S24 = Summer 2024, etc.)
        if re.search(r'(W|S)(2[4-9]|[3-9][0-9])', batch_text):
            return True
        
        # STRICT: If we can't determine, skip it
        return False

    def parse_company_detail(self, response):
        """Parse individual company detail page - FAST with 2024+ filtering"""
        item = response.meta.get('item', YcCompanyItem())
        batch_from_card = response.meta.get('batch_from_card')
        
        # EARLY FILTERING: Check batch before processing - FAST
        # If we already know it's pre-2024 from listing, skip immediately
        if batch_from_card == 'PRE_2024':
            self.skipped_count += 1
            return
        
        # Extract batch from page quickly and filter
        batch_text = self._extract_batch_year(response)
        if batch_text and not self._is_2024_or_later(batch_text):
            self.skipped_count += 1
            if self.skipped_count % 100 == 0:
                print(f'Skipped {self.skipped_count} pre-2024 companies...')
            return  # Skip pre-2024 companies immediately
        
        # If no batch found, include it (better to over-include than miss 2024+ companies)
        # Only skip if we're CERTAIN it's pre-2024
        if not batch_text and not batch_from_card:
            # Include it - can't determine batch, so include to be safe
            pass
        
        self.processed_count += 1
        
        # Extract company name if not already set
        if not item.get('company_name'):
            company_name = (
                response.css('h1::text, h2::text, [class*="company-name"]::text, [class*="CompanyName"]::text').get() or
                response.css('title::text').get()
            )
            if company_name:
                item['company_name'] = company_name.strip().replace(' | Y Combinator', '').strip()
        
        company_name = item.get('company_name', 'Unknown')
        
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
        
        # Extract founder information - PRIMARY METHOD: Extract from LinkedIn URL slugs
        founders_names = []
        founders_linkedin = []
        founders_twitter = []
        
        # Get all unique LinkedIn links
        linkedin_urls = response.css('a[href*="linkedin.com/in/"]::attr(href)').getall()
        linkedin_urls = [url for url in linkedin_urls if url and 'ycombinator.com' not in url]
        
        # Remove duplicates while preserving order
        seen_urls = set()
        unique_linkedin_urls = []
        for url in linkedin_urls:
            # Normalize URL (remove query params, trailing slash)
            normalized = url.split('?')[0].rstrip('/')
            if normalized not in seen_urls:
                seen_urls.add(normalized)
                unique_linkedin_urls.append(normalized)
        
        # Removed debug logging for speed
        
        # PRIMARY METHOD: Extract names from LinkedIn URL slugs
        # LinkedIn URLs like "linkedin.com/in/emre-kaplaner-7b3a3b15b/" contain the name in the slug
        for linkedin_url in unique_linkedin_urls:
            # Extract username from LinkedIn URL: linkedin.com/in/username or linkedin.com/in/username-ID
            match = re.search(r'linkedin\.com/in/([^/?]+)', linkedin_url, re.IGNORECASE)
            if match:
                slug = match.group(1)
                # Remove ID suffix - LinkedIn IDs are often alphanumeric strings at the end
                # Pattern: name-name-XXXXXXXX where X is alphanumeric (usually 8+ chars)
                
                slug_parts = slug.split('-')
                name_parts = []
                
                # Work forwards and stop when we hit an ID-like part
                for part in slug_parts:
                    # Check if this part looks like an ID:
                    # - All digits and longer than 6 chars
                    # - Alphanumeric mix with numbers and length >= 8
                    # - Contains mostly numbers (like "30574a1b0")
                    is_id = False
                    
                    # More aggressive ID detection
                    if part.isdigit() and len(part) > 6:
                        is_id = True
                    elif len(part) >= 8:
                        # Long alphanumeric strings are likely IDs
                        has_digits = any(c.isdigit() for c in part)
                        has_letters = any(c.isalpha() for c in part)
                        
                        if has_digits and has_letters:
                            # Alphanumeric ID pattern (mix of letters and numbers)
                            digit_count = sum(1 for c in part if c.isdigit())
                            # If more than 30% digits, likely an ID
                            if digit_count / len(part) > 0.3:
                                is_id = True
                            # Also check if it looks like a hash (9+ chars with digits and letters)
                            elif len(part) >= 9 and digit_count >= 3:
                                is_id = True
                        elif has_digits and len(part) >= 7:
                            # Mostly numeric
                            is_id = True
                    elif len(part) >= 6 and part.isalnum() and any(c.isdigit() for c in part):
                        # Shorter alphanumeric with numbers might be ID
                        digit_count = sum(1 for c in part if c.isdigit())
                        if part[0].isdigit() or (digit_count / len(part) > 0.4):
                            is_id = True
                    
                    # Additional check: if part is all lowercase and has numbers, likely an ID
                    if not is_id and part.islower() and any(c.isdigit() for c in part) and len(part) >= 7:
                        digit_count = sum(1 for c in part if c.isdigit())
                        if digit_count >= 3:  # At least 3 digits in a lowercase+number mix is suspicious
                            is_id = True
                    
                    if is_id:
                        # Found an ID, stop collecting (everything before this is the name)
                        break
                    else:
                        name_parts.append(part)
                
                # Filter out very short single-character parts unless it's a middle initial
                if len(name_parts) > 1:
                    # Remove single char parts unless they're in the middle (likely initials)
                    filtered_parts = []
                    for idx, part in enumerate(name_parts):
                        if len(part) == 1 and idx > 0 and idx < len(name_parts) - 1:
                            # Middle initial - keep it
                            filtered_parts.append(part)
                        elif len(part) > 1:
                            filtered_parts.append(part)
                        elif len(name_parts) <= 2:
                            # Very short name, keep all parts
                            filtered_parts.append(part)
                    name_parts = filtered_parts if filtered_parts else name_parts
                
                # Need at least 2 parts for a full name, but accept single if it looks like a name
                if len(name_parts) >= 2:
                    name = ' '.join(part.capitalize() for part in name_parts)
                    name = name.strip()  # Clean any extra spaces
                elif len(name_parts) == 1 and len(name_parts[0]) >= 4:
                    # Single word but long enough - might be a valid single name
                    name = name_parts[0].capitalize()
                else:
                    name = None
                
                # Validate and clean the name
                if name:
                    original_name = name
                    # ONLY remove trailing numbers from the LAST word (e.g., "Jha37" -> "Jha")
                    # Don't touch multi-word names - they're likely correct
                    words = name.split()
                    if len(words) == 1 and any(c.isdigit() for c in words[0]):
                        # Single word with digits - remove trailing digits
                        name = re.sub(r'(\w+)\d{2,}$', r'\1', name)
                    name = name.strip()
                    
                    if self._is_valid_name(name, founders_names):
                        founders_names.append(name)
                        founders_linkedin.append(linkedin_url)
                        
                        # Find associated Twitter link near this LinkedIn link
                        slug_first_part = slug.split('-')[0]
                        link_elems = response.css(f'a[href*="linkedin.com/in/"]')
                        for elem in link_elems:
                            href = elem.css('::attr(href)').get() or ''
                            if slug_first_part in href or slug.split('-')[0] in href:
                                container = elem.xpath('./ancestor::div[position()<=4][1] | ./ancestor::section[position()<=3][1]')
                                if container:
                                    twitter = container[0].css('a[href*="twitter.com/"], a[href*="x.com/"]::attr(href)').get()
                                    if twitter and 'ycombinator' not in twitter.lower() and twitter not in founders_twitter:
                                        founders_twitter.append(twitter)
                                    break
        
        # FALLBACK: If we have LinkedIn links but fewer names, try HTML extraction for missing ones
        if len(founders_linkedin) > len(founders_names):
            # Try to find headings near LinkedIn links that we haven't extracted names for
            for linkedin_url in unique_linkedin_urls:
                if linkedin_url in founders_linkedin:
                    # Already have a name for this URL
                    continue
                    
                    # Find the LinkedIn link element
                slug_match = re.search(r'linkedin\.com/in/([^/?]+)', linkedin_url, re.IGNORECASE)
                if not slug_match:
                    continue
                slug_first_part = slug_match.group(1).split('-')[0]
                
                link_elems = response.css(f'a[href*="linkedin.com/in/"]')
                for elem in link_elems:
                    href = elem.css('::attr(href)').get() or ''
                    if slug_first_part in href:
                        # Get parent container
                        container = elem.xpath('./ancestor::div[position()<=5][1] | ./ancestor::section[position()<=3][1] | ./ancestor::article[1]')
                        if container:
                            container_elem = container[0]
                            # Look for heading in this container (skip section titles)
                            headings = container_elem.xpath('.//h1 | .//h2 | .//h3 | .//h4 | .//h5')
                            for heading in headings[:3]:
                                heading_text = heading.xpath('.//text()').get()
                                if heading_text:
                                    heading_text = heading_text.strip()
                                    # Skip section titles
                                    skip_phrases = ['tl;dr', 'our ask', 'our story', 'why we', 'problem:', 'solution:', 
                                                   'the knowledge', 'we are working', 'founders', 'active founders']
                                    if any(skip in heading_text.lower() for skip in skip_phrases):
                                        continue
                                    if self._is_valid_name(heading_text, founders_names):
                                        founders_names.append(heading_text)
                                        founders_linkedin.append(linkedin_url)
                                        
                                        # Get Twitter if available
                                        twitter = container_elem.css('a[href*="twitter.com/"], a[href*="x.com/"]::attr(href)').get()
                                        if twitter and 'ycombinator' not in twitter.lower() and twitter not in founders_twitter:
                                            founders_twitter.append(twitter)
                                        break
                        break
        
        # Ensure lists are aligned - pad with empty strings if needed
        # But only align if we have at least one item in any list
        max_len = max(len(founders_names), len(founders_linkedin), len(founders_twitter))
        if max_len > 0:
            while len(founders_names) < max_len:
                founders_names.append('')
            while len(founders_linkedin) < max_len:
                founders_linkedin.append('')
            while len(founders_twitter) < max_len:
                founders_twitter.append('')
        
        # Final cleanup - remove @ycombinator from Twitter if somehow included
        founders_twitter = [t for t in founders_twitter if t and 'ycombinator' not in t.lower()]
        
        # Final cleanup of founder names - REMOVED aggressive cleanup that was truncating valid names
        # Only remove trailing digits from single words (e.g., "Jha37" -> "Jha")
        cleaned_names = []
        for name in founders_names:
            if not name:
                continue
            cleaned = name.strip()
            # Only remove trailing digits from single-word names with digits
            words = cleaned.split()
            if len(words) == 1 and any(c.isdigit() for c in words[0]):
                # Single word with digits - remove trailing 2+ digits
                cleaned = re.sub(r'(\w+)\d{2,}$', r'\1', cleaned).strip()
            
            if cleaned and cleaned not in cleaned_names:
                cleaned_names.append(cleaned)
        
        founders_names = cleaned_names
        
        # Set item fields
        item['founders_name'] = ', '.join(set(founders_names)) if founders_names else ''
        item['founders_linkedin'] = ', '.join(set(founders_linkedin)) if founders_linkedin else ''
        item['founders_twitter'] = ', '.join(set(founders_twitter)) if founders_twitter else ''
        
        # Print progress every 50 companies
        if self.processed_count % 50 == 0:
            print(f'Processed {self.processed_count} companies (2024+), skipped {self.skipped_count} pre-2024...')
        
        # Always yield if we have a company name, even if no founders were found
        if item.get('company_name'):
            yield item
        else:
            # Log and try to extract company name from URL or page
            try:
                # Try to get company name from URL slug
                url_slug = response.url.split('/')[-1]
                if url_slug:
                    item['company_name'] = url_slug.replace('-', ' ').title()
                    self.logger.warning(f'Company name not found for {response.url}, using URL slug: {item["company_name"]}')
                    yield item
                else:
                    self.logger.warning(f'No company name found for {response.url}')
            except:
                self.logger.warning(f'No company name found for {response.url}')

