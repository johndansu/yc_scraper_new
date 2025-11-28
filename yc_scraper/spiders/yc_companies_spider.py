import scrapy
from yc_scraper.items import YcCompanyItem
import re
import os
from datetime import datetime


class YcCompaniesSpider(scrapy.Spider):
    name = 'yc_companies'
    allowed_domains = ['ycombinator.com']
    
    start_urls = [
        'https://www.ycombinator.com/companies?batch=Fall%202024&batch=Winter%202024&batch=Summer%202024&batch=Winter%202025&batch=Spring%202025&batch=Summer%202025&batch=Fall%202025&batch=Winter%202026'
    ]
    
    def __init__(self, *args, **kwargs):
        super(YcCompaniesSpider, self).__init__(*args, **kwargs)
        self._init_debug_log()
    
    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(YcCompaniesSpider, cls).from_crawler(crawler, *args, **kwargs)
        spider._init_debug_log()
        return spider
    
    def _init_debug_log(self):
        """Initialize the debug log file"""
        if hasattr(self, 'debug_log') and self.debug_log:
            return  # Already initialized
        
        debug_file = 'founder_debug_log.txt'
        debug_path = os.path.abspath(debug_file)
        
        try:
            self.debug_log = open(debug_file, 'w', encoding='utf-8')
            self.debug_log.write(f"=== FOUNDER EXTRACTION DEBUG LOG ===\n")
            self.debug_log.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            self.debug_log.write(f"Debug log location: {debug_path}\n\n")
            self.debug_log.flush()
            print(f"\n{'='*60}")
            print(f"DEBUG LOG FILE CREATED!")
            print(f"Location: {debug_path}")
            print(f"{'='*60}\n")
        except Exception as e:
            print(f"ERROR: Could not create debug log file: {e}")
            import io
            self.debug_log = io.StringIO()
    
    def closed(self, reason):
        """Called when spider closes"""
        if hasattr(self, 'debug_log') and self.debug_log:
            try:
                self.debug_log.write(f"\n=== END OF LOG ===\n")
                self.debug_log.write(f"Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                self.debug_log.close()
            except:
                pass

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

    def parse(self, response):
        """Parse the Y Combinator companies page"""
        self.logger.info(f'Parsing page: {response.url}')
        
        # Y Combinator uses specific structure - try multiple selectors
        # Common patterns: links to /companies/, divs with company info
        company_links = response.css('a[href*="/companies/"]:not([href*="/companies?"])')
        
        # Also try to find company cards/items with broader selectors
        company_cards = response.css(
            '[class*="CompanyCard"], [class*="company-card"], '
            '[data-testid*="company"], [class*="Company"], '
            'a[href^="/companies/"]'
        )
        
        # Combine both approaches and remove duplicates
        all_companies = []
        seen_urls = set()
        
        for element in list(company_links) + list(company_cards):
            href = element.css('::attr(href)').get() or ''
            # Normalize URL
            if '/companies/' in href:
                # Extract just the company slug part for deduplication
                company_slug = href.split('/companies/')[-1].split('?')[0].split('#')[0]
                if company_slug and company_slug not in seen_urls and company_slug != 'companies':
                    seen_urls.add(company_slug)
                    all_companies.append(element)
        
        if not all_companies:
            # Fallback: try to find any link containing company info (more broadly)
            all_links = response.css('a[href*="companies"]')
            for element in all_links:
                href = element.css('::attr(href)').get() or ''
                if '/companies/' in href and 'companies?' not in href:
                    company_slug = href.split('/companies/')[-1].split('?')[0].split('#')[0]
                    if company_slug and company_slug not in seen_urls and company_slug != 'companies':
                        seen_urls.add(company_slug)
                        all_companies.append(element)
        
        self.logger.info(f'Found {len(all_companies)} potential company links')
        
        # Debug log
        try:
            if hasattr(self, 'debug_log') and self.debug_log:
                self.debug_log.write(f"\nPARSING MAIN PAGE: {response.url}\n")
                self.debug_log.write(f"Found {len(all_companies)} potential company links\n")
                self.debug_log.flush()
        except:
            pass
        
        processed_urls = set()
        company_count = 0
        
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
                company_count += 1
                try:
                    if hasattr(self, 'debug_log') and self.debug_log:
                        self.debug_log.write(f"  Requesting company #{company_count}: {full_url}\n")
                        if company_count <= 5:  # Only flush first 5
                            self.debug_log.flush()
                except:
                    pass
                
                yield scrapy.Request(
                    full_url,
                    callback=self.parse_company_detail,
                    meta={'item': item}
                )

    def parse_company_detail(self, response):
        """Parse individual company detail page for more information"""
        item = response.meta.get('item', YcCompanyItem())
        
        # Initialize debug log if not already done
        if not hasattr(self, 'debug_log') or self.debug_log is None:
            self._init_debug_log()
        
        # Extract company name if not already set
        if not item.get('company_name'):
            company_name = (
                response.css('h1::text, h2::text, [class*="company-name"]::text, [class*="CompanyName"]::text').get() or
                response.css('title::text').get()
            )
            if company_name:
                item['company_name'] = company_name.strip().replace(' | Y Combinator', '').strip()
        
        company_name = item.get('company_name', 'Unknown')
        
        # Write to debug log
        try:
            self.debug_log.write(f"\n{'='*80}\n")
            self.debug_log.write(f"COMPANY: {company_name}\n")
            self.debug_log.write(f"URL: {response.url}\n")
            self.debug_log.flush()
        except:
            pass
        
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
        
        try:
            self.debug_log.write(f"LinkedIn links found: {len(unique_linkedin_urls)}\n")
            if unique_linkedin_urls:
                for i, url in enumerate(unique_linkedin_urls[:5], 1):
                    self.debug_log.write(f"  {i}. {url}\n")
            self.debug_log.flush()
        except:
            pass
        
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
                
                # Debug: log the slug parts
                try:
                    self.debug_log.write(f"    Processing slug: {slug}, parts: {slug_parts}\n")
                    self.debug_log.flush()
                except:
                    pass
                
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
                        try:
                            self.debug_log.write(f"      Detected ID part: '{part}', stopping. Name parts so far: {name_parts}\n")
                            self.debug_log.flush()
                        except:
                            pass
                        break
                    else:
                        name_parts.append(part)
                
                # Debug: log name parts before filtering
                try:
                    self.debug_log.write(f"    Name parts before filtering: {name_parts}\n")
                    self.debug_log.flush()
                except:
                    pass
                
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
                
                # Debug: log name parts after filtering
                try:
                    self.debug_log.write(f"    Name parts after filtering: {name_parts}\n")
                    self.debug_log.flush()
                except:
                    pass
                
                # Need at least 2 parts for a full name, but accept single if it looks like a name
                if len(name_parts) >= 2:
                    name = ' '.join(part.capitalize() for part in name_parts)
                    name = name.strip()  # Clean any extra spaces
                elif len(name_parts) == 1 and len(name_parts[0]) >= 4:
                    # Single word but long enough - might be a valid single name
                    name = name_parts[0].capitalize()
                else:
                    name = None
                
                # Debug: log final name
                try:
                    self.debug_log.write(f"    Extracted name: '{name}' (from {len(name_parts)} parts)\n")
                    self.debug_log.flush()
                except:
                    pass
                
                # Validate and clean the name
                if name:
                    # Remove any trailing alphanumeric IDs that might have slipped through
                    # Only remove if it's clearly an ID (has digits and is at the end)
                    original_name = name
                    # Remove trailing IDs: patterns like "Name 7b3a3b15b" or "Name 1234567"
                    name = re.sub(r'\s+[a-z]*\d+[a-z\d]{6,}$', '', name, flags=re.IGNORECASE)  # Trailing ID with 6+ chars after digit
                    name = re.sub(r'\s+\d{7,}$', '', name)  # Trailing 7+ digit IDs
                    # Only remove if the trailing part has significant digits
                    name = re.sub(r'\s+[a-z\d]{8,}$', '', name, flags=re.IGNORECASE)  # Only if trailing part is 8+ chars (likely ID)
                    name = name.strip()
                    
                    # Debug: log if name was modified
                    if name != original_name:
                        try:
                            self.debug_log.write(f"  Cleaned '{original_name}' -> '{name}'\n")
                            self.debug_log.flush()
                        except:
                            pass
                    
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
        
        # Final cleanup of founder names - remove any trailing IDs that slipped through
        cleaned_names = []
        for name in founders_names:
            if not name:
                continue
            # Remove trailing alphanumeric IDs (more aggressive patterns)
            cleaned = re.sub(r'\s+[a-z0-9]{7,}$', '', name, flags=re.IGNORECASE)
            # Remove trailing numeric IDs (6+ digits)
            cleaned = re.sub(r'\s+\d{6,}$', '', cleaned)
            # Remove patterns like "word 123abc456" (alphanumeric with numbers)
            cleaned = re.sub(r'\s+[a-z]*\d+[a-z\d]{5,}$', '', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'\s+\d+[a-z]+\d*[a-z\d]{4,}$', '', cleaned, flags=re.IGNORECASE)
            # Remove any remaining trailing spaces
            cleaned = cleaned.strip()
            # Check if the last word looks like an ID and remove it (but be careful not to remove valid names)
            words = cleaned.split()
            if len(words) > 1:  # Only remove last word if there are multiple words
                last_word = words[-1]
                # If last word looks like an ID (8+ chars with mix of digits and letters), remove it
                if (len(last_word) >= 8 and any(c.isdigit() for c in last_word) and 
                    any(c.isalpha() for c in last_word)):
                    digit_count = sum(1 for c in last_word if c.isdigit())
                    # Only remove if it's clearly an ID (50%+ digits in an 8+ char string)
                    if digit_count / len(last_word) > 0.5:
                        words = words[:-1]
                        cleaned = ' '.join(words).strip()
            if cleaned and cleaned not in cleaned_names:
                cleaned_names.append(cleaned)
        
        founders_names = cleaned_names
        
        # Set item fields
        item['founders_name'] = ', '.join(set(founders_names)) if founders_names else ''
        item['founders_linkedin'] = ', '.join(set(founders_linkedin)) if founders_linkedin else ''
        item['founders_twitter'] = ', '.join(set(founders_twitter)) if founders_twitter else ''
        
        # Final debug summary
        try:
            self.debug_log.write(f"\nFINAL RESULTS for {company_name}:\n")
            if founders_names:
                self.debug_log.write(f"✓ Found {len(founders_names)} founder(s): {', '.join(founders_names)}\n")
            else:
                self.debug_log.write(f"✗ NO FOUNDER NAMES FOUND\n")
            self.debug_log.write(f"{'='*80}\n\n")
            self.debug_log.flush()
        except:
            pass
        
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

