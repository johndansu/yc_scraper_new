@echo off
echo Running Y Combinator Companies Scraper...
echo.

scrapy crawl yc_companies

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Scraping completed successfully!
    echo Data saved to: yc_companies.xlsx
) else (
    echo.
    echo Error occurred during scraping.
    echo Make sure you have installed all dependencies:
    echo   pip install -r requirements.txt
)

pause

