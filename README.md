# Amazon Reviews Scraper

A Python script to scrape all reviews from any Amazon product page and save them as a JSON file.

## Features

- ✓ Scrapes ALL reviews with automatic pagination handling
- ✓ Extracts comprehensive review data:
  - Review ID, title, and body text
  - Star rating (1-5)
  - Reviewer name
  - Review date
  - Verified purchase status
  - Helpful vote counts
  - Product variant/configuration
  - Review images
  - Vine and Early Reviewer badges
  - Review permalink
- ✓ Progress tracking during scraping
- ✓ Random delays between requests to avoid blocking
- ✓ Automatic retry logic for network errors
- ✓ Graceful error handling
- ✓ Clean JSON output format

## Installation

1. Install required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

```bash
python amazon_reviews_scraper.py "https://www.amazon.com/dp/YOUR_PRODUCT_ASIN"
```

### Advanced Usage

```bash
# Limit to first 10 pages
python amazon_reviews_scraper.py "https://www.amazon.com/dp/YOUR_PRODUCT_ASIN" --max-pages 10

# Custom output filename
python amazon_reviews_scraper.py "https://www.amazon.com/dp/YOUR_PRODUCT_ASIN" --output my_reviews.json

# Custom delay range (3-7 seconds between requests)
python amazon_reviews_scraper.py "https://www.amazon.com/dp/YOUR_PRODUCT_ASIN" --delay 3 7

# Enable debug mode (saves HTML files for inspection)
python amazon_reviews_scraper.py "https://www.amazon.com/dp/YOUR_PRODUCT_ASIN" --debug

# Combine options
python amazon_reviews_scraper.py "https://www.amazon.com/dp/YOUR_PRODUCT_ASIN" --max-pages 5 --output custom.json --delay 1 3
```

## Command Line Options

- `--max-pages N` - Maximum number of pages to scrape (default: all pages)
- `--output FILE` - Output filename (default: amazon_reviews.json)
- `--delay MIN MAX` - Delay range in seconds between requests (default: 2 5)
- `--debug` - Enable debug mode (saves HTML files when no reviews found)

## Output Format

The script generates a JSON file with the following structure:

```json
{
  "product_asin": "B08N5WRWNW",
  "product_title": "Example Product Name",
  "product_url": "https://www.amazon.com/dp/B08N5WRWNW",
  "total_reviews": 150,
  "scrape_date": "2025-01-15T10:30:00",
  "reviews": [
    {
      "review_id": "R1234567890ABC",
      "title": "Great product!",
      "body": "This product exceeded my expectations...",
      "rating": 5.0,
      "author": "John Doe",
      "date": "January 10, 2025",
      "verified_purchase": true,
      "helpful_votes": 42,
      "product_variant": "Color: Black | Size: Medium",
      "images": [
        "https://images-na.ssl-images-amazon.com/images/..."
      ],
      "permalink": "https://www.amazon.com/gp/customer-reviews/...",
      "vine_review": false,
      "early_reviewer": false
    }
  ]
}
```

## How It Works

1. **ASIN Extraction**: Extracts the product ASIN from the provided Amazon URL
2. **Page Navigation**: Automatically handles pagination to fetch all review pages
3. **Data Extraction**: Parses each review using BeautifulSoup to extract all available information
4. **Progress Display**: Shows real-time progress including page number and reviews count
5. **Smart Delays**: Implements random delays between requests to avoid rate limiting
6. **Error Handling**: Includes retry logic for network errors and graceful failure handling
7. **JSON Export**: Saves all scraped data to a well-structured JSON file

## Important Notes

- **Rate Limiting**: The scraper includes delays between requests to be respectful to Amazon's servers
- **Blocking Risk**: Amazon may block requests if scraping too aggressively. Use reasonable delays.
- **Amazon's Terms**: Web scraping may violate Amazon's Terms of Service. Use responsibly and at your own risk.
- **Dynamic Content**: This scraper uses requests/BeautifulSoup. If Amazon's page structure changes significantly, the scraper may need updates.
- **Interruption**: Press Ctrl+C to stop scraping. You'll be prompted to save partial results.

## Troubleshooting

### No reviews found

If the scraper reports no reviews found:

1. **Verify the product URL** - Make sure the URL is a valid Amazon product page with reviews
2. **Use debug mode** - Run with `--debug` flag to save HTML files for inspection:
   ```bash
   python amazon_reviews_scraper.py "YOUR_URL" --debug
   ```
   This will create `debug_page_1.html` files you can open in a browser to see what Amazon returned

3. **Check for blocking** - The scraper will detect CAPTCHA and blocking messages
   - If blocked, try: Using a VPN, increasing delays, or waiting before trying again
   - Amazon actively blocks scrapers

4. **Check debug output** - When debug mode is enabled, you'll see:
   - Number of review elements found
   - All data-hook values on the page
   - Detailed parsing errors

### Request errors

- Check your internet connection
- Try increasing the delay between requests: `--delay 3 7`
- Amazon may be blocking your IP temporarily - try again later or use a VPN

### Being blocked by Amazon

Amazon actively tries to block automated scraping. Signs you're blocked:
- CAPTCHA page displayed
- "Robot Check" message
- Empty reviews despite product having reviews

**Solutions:**
- Increase delays: `--delay 5 10`
- Use a VPN to change your IP
- Try from a different network
- Wait a few hours before trying again
- Consider using Amazon's official API instead

### Parsing errors

- Amazon's page structure may have changed - check for scraper updates
- Some review fields may not be available for all reviews (expected behavior)

## Example

```bash
python amazon_reviews_scraper.py "https://www.amazon.com/dp/B08N5WRWNW"
```

Output:
```
============================================================
Amazon Reviews Scraper
============================================================

Starting to scrape reviews for ASIN: B08N5WRWNW
Product URL: https://www.amazon.com/dp/B08N5WRWNW

Scraping page 1...
Product: Example Product Name
Total reviews available: 1234

  Found 10 reviews on page 1 (Total: 10)
  Waiting 3.2s before next page...
Scraping page 2...
  Found 10 reviews on page 2 (Total: 20)
  ...
```

## License

This project is provided as-is for educational purposes.
