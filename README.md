# Y Combinator Companies Scraper

A Scrapy-based web scraper to extract company information from Y Combinator's companies directory. The scraper uses Selenium to handle dynamic JavaScript content and exports data to Excel format.

## Features

- Scrapes company data from Y Combinator's companies page
- Handles dynamic content using Selenium
- Exports data to Excel format (.xlsx)
- Extracts the following information:
  - Company Name
  - Company Website
  - Founder's Name
  - Founders LinkedIn
  - Founders Twitter (Optional)

## Prerequisites

- Python 3.7 or higher
- Chrome browser (or Firefox) installed
- ChromeDriver (or GeckoDriver for Firefox) - should be in your PATH

### Installing ChromeDriver

**Windows:**
1. Download ChromeDriver from https://chromedriver.chromium.org/
2. Extract and add to your system PATH
3. Or place chromedriver.exe in the project directory

**macOS:**
```bash
brew install chromedriver
```

**Linux:**
```bash
# Download and install ChromeDriver
wget https://chromedriver.storage.googleapis.com/LATEST_RELEASE/chromedriver_linux64.zip
unzip chromedriver_linux64.zip
sudo mv chromedriver /usr/local/bin/
```

## Installation

1. Install the required packages:
```bash
pip install -r requirements.txt
```

## Usage

Run the spider with:
```bash
scrapy crawl yc_companies
```

The output will be saved to `yc_companies.xlsx` in the project root directory.

### Customizing the URL

To scrape different batches, edit the `start_urls` in `yc_scraper/spiders/yc_companies_spider.py`:

```python
start_urls = [
    'https://www.ycombinator.com/companies?batch=Fall%202024&batch=Winter%202024'
]
```

## Project Structure

```
yc_scraper_new/
├── scrapy.cfg              # Scrapy configuration file
├── yc_scraper/
│   ├── __init__.py
│   ├── items.py            # Item definitions
│   ├── middlewares.py      # Selenium middleware
│   ├── pipelines.py        # Excel export pipeline
│   ├── settings.py         # Scrapy settings
│   └── spiders/
│       ├── __init__.py
│       └── yc_companies_spider.py  # Main spider
├── requirements.txt
└── README.md
```

## Configuration

### Adjusting Download Delay

Edit `yc_scraper/settings.py` to change the delay between requests:
```python
DOWNLOAD_DELAY = 2  # seconds
```

### Disabling Headless Mode

To see the browser in action, edit `yc_scraper/middlewares.py`:
```python
chrome_options.add_argument('--headless')  # Remove this line
```

## Troubleshooting

1. **ChromeDriver not found**: Make sure ChromeDriver is installed and in your PATH
2. **No data extracted**: The page structure may have changed. Check the CSS selectors in the spider
3. **Timeout errors**: Increase the wait time in the Selenium middleware

## Notes

- The scraper respects rate limiting with a 2-second delay between requests
- The scraper scrolls the page to load all companies (handles infinite scroll)
- Some fields may be empty if the information is not available on the page

## License

This project is for educational purposes only. Please respect Y Combinator's robots.txt and terms of service.

