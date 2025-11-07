#!/usr/bin/env python3
"""
Amazon Product Reviews Scraper
Scrapes all reviews from an Amazon product page and saves them to a JSON file.
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse, parse_qs
import random
import sys
import os


class AmazonReviewsScraper:
    """Scraper for Amazon product reviews."""

    def __init__(self, product_url: str, debug: bool = False):
        """
        Initialize the scraper with a product URL.

        Args:
            product_url: The Amazon product page URL
            debug: Enable debug mode (saves HTML files for inspection)
        """
        self.product_url = product_url
        self.asin = self._extract_asin(product_url)
        self.reviews = []
        self.product_title = ""
        self.debug = debug

        # Headers to mimic a real browser
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'DNT': '1',
        }

        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def _extract_asin(self, url: str) -> str:
        """
        Extract ASIN from Amazon product URL.

        Args:
            url: Amazon product URL

        Returns:
            ASIN string
        """
        # Try to extract from /dp/ pattern
        match = re.search(r'/dp/([A-Z0-9]{10})', url)
        if match:
            return match.group(1)

        # Try to extract from /product/ pattern
        match = re.search(r'/product/([A-Z0-9]{10})', url)
        if match:
            return match.group(1)

        # Try to extract from /gp/product/ pattern
        match = re.search(r'/gp/product/([A-Z0-9]{10})', url)
        if match:
            return match.group(1)

        # Try ASIN query parameter
        match = re.search(r'[?&]asin=([A-Z0-9]{10})', url)
        if match:
            return match.group(1)

        raise ValueError(f"Could not extract ASIN from URL: {url}")

    def _get_reviews_url(self, page_number: int = 1) -> str:
        """
        Construct the reviews URL for a given page number.

        Args:
            page_number: Page number to fetch

        Returns:
            Reviews page URL
        """
        # Simplified URL format that works more reliably
        base_url = f"https://www.amazon.com/product-reviews/{self.asin}"
        if page_number > 1:
            return f"{base_url}?pageNumber={page_number}"
        return base_url

    def _check_for_blocking(self, soup: BeautifulSoup, response: requests.Response) -> bool:
        """
        Check if Amazon is blocking or showing CAPTCHA.

        Args:
            soup: BeautifulSoup object of the page
            response: Response object

        Returns:
            True if blocked, False otherwise
        """
        # Check for common blocking indicators
        if "api-services-support@amazon.com" in response.text:
            print("\n⚠ WARNING: Amazon detected automated access!")
            return True

        if "Robot Check" in response.text or "Enter the characters you see below" in response.text:
            print("\n⚠ WARNING: CAPTCHA detected!")
            return True

        if response.status_code == 503:
            print("\n⚠ WARNING: Service unavailable (503)")
            return True

        return False

    def _save_debug_html(self, html_content: str, page_number: int):
        """
        Save HTML content to file for debugging.

        Args:
            html_content: HTML content to save
            page_number: Page number for filename
        """
        if self.debug:
            filename = f"debug_page_{page_number}.html"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"  [DEBUG] Saved HTML to {filename}")

    def _parse_review(self, review_element) -> Optional[Dict]:
        """
        Parse a single review element and extract all information.

        Args:
            review_element: BeautifulSoup element containing review

        Returns:
            Dictionary with review data or None if parsing failed
        """
        try:
            review_data = {}

            # Review ID
            review_id = review_element.get('id', '')
            review_data['review_id'] = review_id

            # Review title - try multiple selectors
            title_elem = review_element.find('a', {'data-hook': 'review-title'})
            if not title_elem:
                title_elem = review_element.find('span', {'data-hook': 'review-title'})

            if title_elem:
                # Sometimes title has nested spans
                title_text = title_elem.get_text(strip=True)
                # Remove star rating prefix if present (e.g., "5.0 out of 5 stars Great!")
                title_text = re.sub(r'^[\d.]+\s+out of \d+\s+stars\s*', '', title_text)
                review_data['title'] = title_text
            else:
                review_data['title'] = ""

            # Review body
            body_elem = review_element.find('span', {'data-hook': 'review-body'})
            if body_elem:
                # Get all text, handling nested spans
                body_text = body_elem.get_text(strip=True)
                # Sometimes has "Read more" text
                body_text = re.sub(r'\s*Read more\s*$', '', body_text)
                review_data['body'] = body_text
            else:
                review_data['body'] = ""

            # Star rating - try multiple approaches
            rating = 0
            rating_elem = review_element.find('i', {'data-hook': 'review-star-rating'})
            if not rating_elem:
                rating_elem = review_element.find('i', class_=re.compile(r'a-star-\d'))

            if rating_elem:
                # Try to extract from class name (e.g., "a-star-5")
                classes = rating_elem.get('class', [])
                for cls in classes:
                    match = re.search(r'a-star-(\d+(?:-\d+)?)', cls)
                    if match:
                        rating_str = match.group(1).replace('-', '.')
                        rating = float(rating_str)
                        break

                # Fallback: extract from text
                if rating == 0:
                    rating_text = rating_elem.get_text(strip=True)
                    rating_match = re.search(r'([\d.]+)', rating_text)
                    if rating_match:
                        rating = float(rating_match.group(1))

            review_data['rating'] = rating

            # Author name
            author_elem = review_element.find('span', class_='a-profile-name')
            review_data['author'] = author_elem.get_text(strip=True) if author_elem else ""

            # Review date
            date_elem = review_element.find('span', {'data-hook': 'review-date'})
            date_text = date_elem.get_text(strip=True) if date_elem else ""
            # Extract date from text like "Reviewed in the United States on January 1, 2024"
            date_match = re.search(r'on\s+(.+)$', date_text)
            review_data['date'] = date_match.group(1) if date_match else date_text

            # Verified purchase status
            verified_elem = review_element.find('span', {'data-hook': 'avp-badge'})
            review_data['verified_purchase'] = verified_elem is not None

            # Helpful votes count
            helpful_elem = review_element.find('span', {'data-hook': 'helpful-vote-statement'})
            helpful_votes = 0
            if helpful_elem:
                helpful_text = helpful_elem.get_text(strip=True)
                # Extract number from text like "123 people found this helpful"
                helpful_match = re.search(r'([\d,]+)', helpful_text)
                if helpful_match:
                    helpful_votes = int(helpful_match.group(1).replace(',', ''))
                elif 'One person found this helpful' in helpful_text:
                    helpful_votes = 1
            review_data['helpful_votes'] = helpful_votes

            # Product variant/configuration
            variant_elem = review_element.find('a', {'data-hook': 'format-strip'})
            review_data['product_variant'] = variant_elem.get_text(strip=True) if variant_elem else ""

            # Review images
            images = []
            # Try different image selectors
            image_elements = review_element.find_all('img', class_=re.compile(r'review-image'))
            if not image_elements:
                image_elements = review_element.find_all('img', {'data-hook': 'review-image-tile'})

            for img in image_elements:
                img_url = img.get('src', '')
                if not img_url:
                    img_url = img.get('data-src', '')
                if img_url and 'amazon.com' in img_url:
                    images.append(img_url)
            review_data['images'] = images

            # Review permalink
            permalink_elem = review_element.find('a', {'data-hook': 'review-title'})
            if permalink_elem and permalink_elem.get('href'):
                review_data['permalink'] = urljoin('https://www.amazon.com', permalink_elem['href'])
            else:
                review_data['permalink'] = ""

            # Vine program
            vine_elem = review_element.find('span', {'data-hook': 'vine-badge'})
            review_data['vine_review'] = vine_elem is not None

            # Early reviewer rewards
            early_reviewer_elem = review_element.find('span', {'data-hook': 'early-reviewer-badge'})
            review_data['early_reviewer'] = early_reviewer_elem is not None

            return review_data

        except Exception as e:
            if self.debug:
                print(f"  [DEBUG] Error parsing review: {e}")
                import traceback
                traceback.print_exc()
            return None

    def _get_product_title(self, soup: BeautifulSoup) -> str:
        """
        Extract product title from the reviews page.

        Args:
            soup: BeautifulSoup object of the page

        Returns:
            Product title string
        """
        # Try different selectors for product title
        title_elem = soup.find('a', {'data-hook': 'product-link'})
        if title_elem:
            return title_elem.get_text(strip=True)

        title_elem = soup.find('h1', class_='a-size-large')
        if title_elem:
            return title_elem.get_text(strip=True)

        # Try alt approach
        title_elem = soup.find('a', class_='a-link-normal', href=re.compile(r'/dp/'))
        if title_elem:
            return title_elem.get_text(strip=True)

        return "Unknown Product"

    def _get_total_reviews_count(self, soup: BeautifulSoup) -> int:
        """
        Extract total number of reviews from the page.

        Args:
            soup: BeautifulSoup object of the page

        Returns:
            Total reviews count
        """
        # Try to find the total reviews count
        count_elem = soup.find('div', {'data-hook': 'cr-filter-info-review-rating-count'})
        if count_elem:
            text = count_elem.get_text(strip=True)
            # Extract number from text like "1,234 global ratings | 567 global reviews"
            match = re.search(r'([\d,]+)\s+global reviews', text)
            if match:
                return int(match.group(1).replace(',', ''))
            # Try extracting first number
            match = re.search(r'([\d,]+)', text)
            if match:
                return int(match.group(1).replace(',', ''))

        # Try alternative selector
        count_elem = soup.find('div', {'data-hook': 'total-review-count'})
        if count_elem:
            text = count_elem.get_text(strip=True)
            match = re.search(r'([\d,]+)', text)
            if match:
                return int(match.group(1).replace(',', ''))

        return 0

    def scrape_reviews(self, max_pages: Optional[int] = None, delay_range: tuple = (2, 5)) -> Dict:
        """
        Scrape all reviews from the product.

        Args:
            max_pages: Maximum number of pages to scrape (None for all pages)
            delay_range: Tuple of (min, max) seconds to wait between requests

        Returns:
            Dictionary with all scraped data
        """
        print(f"Starting to scrape reviews for ASIN: {self.asin}")
        print(f"Product URL: {self.product_url}")
        if self.debug:
            print(f"[DEBUG MODE ENABLED]")
        print()

        page_number = 1
        total_scraped = 0
        consecutive_empty_pages = 0
        max_consecutive_empty = 3

        while True:
            # Check if we've reached max pages
            if max_pages and page_number > max_pages:
                print(f"\nReached maximum page limit: {max_pages}")
                break

            # Construct reviews URL
            reviews_url = self._get_reviews_url(page_number)

            print(f"Scraping page {page_number}: {reviews_url}")

            try:
                # Make request with retry logic
                max_retries = 3
                response = None
                for attempt in range(max_retries):
                    try:
                        response = self.session.get(reviews_url, timeout=30)
                        response.raise_for_status()
                        break
                    except requests.exceptions.RequestException as e:
                        if attempt < max_retries - 1:
                            wait_time = (attempt + 1) * 2
                            print(f"  Request failed, retrying in {wait_time}s... ({attempt + 1}/{max_retries})")
                            time.sleep(wait_time)
                        else:
                            raise

                if not response:
                    print("  Failed to get response after retries")
                    break

                # Parse HTML
                soup = BeautifulSoup(response.content, 'html.parser')

                # Check for blocking/CAPTCHA
                if self._check_for_blocking(soup, response):
                    self._save_debug_html(response.text, page_number)
                    print("\nStopping due to blocking detection.")
                    print("Try: 1) Using a VPN, 2) Increasing delays, 3) Trying again later")
                    break

                # Get product title from first page
                if page_number == 1:
                    self.product_title = self._get_product_title(soup)
                    total_reviews = self._get_total_reviews_count(soup)
                    print(f"Product: {self.product_title}")
                    print(f"Total reviews available: {total_reviews}")
                    print()

                # Find all review elements - try multiple selectors
                review_elements = soup.find_all('div', {'data-hook': 'review'})

                if self.debug:
                    print(f"  [DEBUG] Found {len(review_elements)} review elements with data-hook='review'")

                    # Debug: Show what divs are on the page
                    all_divs_with_data_hook = soup.find_all('div', attrs={'data-hook': True})
                    print(f"  [DEBUG] Total divs with data-hook: {len(all_divs_with_data_hook)}")
                    data_hooks = set([div.get('data-hook') for div in all_divs_with_data_hook])
                    print(f"  [DEBUG] Unique data-hook values: {data_hooks}")

                if not review_elements:
                    consecutive_empty_pages += 1
                    print(f"  No reviews found on page {page_number}")

                    # Save HTML for inspection
                    self._save_debug_html(response.text, page_number)

                    if consecutive_empty_pages >= max_consecutive_empty:
                        print(f"\nNo reviews found on {max_consecutive_empty} consecutive pages. Stopping.")
                        if page_number == 1:
                            print("\n⚠ Troubleshooting tips:")
                            print("  1. Verify the product has reviews on Amazon")
                            print("  2. Check if you're being blocked (see debug HTML file)")
                            print("  3. Try using --debug flag to save HTML for inspection")
                            print("  4. The product URL might be invalid")
                        break

                    # Wait and try next page
                    time.sleep(random.uniform(*delay_range))
                    page_number += 1
                    continue

                # Reset consecutive empty pages counter
                consecutive_empty_pages = 0

                # Parse each review
                page_reviews = 0
                for review_elem in review_elements:
                    review_data = self._parse_review(review_elem)
                    if review_data:
                        self.reviews.append(review_data)
                        page_reviews += 1
                        total_scraped += 1

                print(f"  ✓ Found {page_reviews} reviews on page {page_number} (Total: {total_scraped})")

                # Check if there's a next page
                next_button = soup.find('li', class_='a-last')
                if not next_button or 'a-disabled' in next_button.get('class', []):
                    print(f"\nReached last page (page {page_number})")
                    break

                # Random delay between requests to avoid being blocked
                delay = random.uniform(*delay_range)
                print(f"  Waiting {delay:.1f}s before next page...")
                time.sleep(delay)

                page_number += 1

            except requests.exceptions.RequestException as e:
                print(f"\n⚠ Error fetching page {page_number}: {e}")
                print("Stopping scrape due to network error.")
                break
            except Exception as e:
                print(f"\n⚠ Unexpected error on page {page_number}: {e}")
                if self.debug:
                    import traceback
                    traceback.print_exc()
                print("Stopping scrape due to error.")
                break

        print(f"\n{'='*60}")
        print(f"Scraping completed!")
        print(f"Total reviews scraped: {len(self.reviews)}")
        print(f"Pages processed: {page_number}")
        print(f"{'='*60}\n")

        # Prepare output data
        output_data = {
            'product_asin': self.asin,
            'product_title': self.product_title,
            'product_url': self.product_url,
            'total_reviews': len(self.reviews),
            'scrape_date': datetime.now().isoformat(),
            'reviews': self.reviews
        }

        return output_data

    def save_to_json(self, output_data: Dict, filename: str = 'amazon_reviews.json'):
        """
        Save scraped reviews to a JSON file.

        Args:
            output_data: Dictionary containing all scraped data
            filename: Output filename
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            print(f"✓ Reviews saved to: {filename}")
        except Exception as e:
            print(f"⚠ Error saving to JSON: {e}")
            raise


def main():
    """Main function to run the scraper."""

    # Check if URL is provided
    if len(sys.argv) < 2:
        print("Amazon Reviews Scraper")
        print("=" * 60)
        print("\nUsage:")
        print("  python amazon_reviews_scraper.py <AMAZON_PRODUCT_URL> [OPTIONS]")
        print("\nOptions:")
        print("  --max-pages N    Maximum number of pages to scrape (default: all)")
        print("  --output FILE    Output filename (default: amazon_reviews.json)")
        print("  --delay MIN MAX  Delay range in seconds between requests (default: 2 5)")
        print("  --debug          Enable debug mode (saves HTML files for inspection)")
        print("\nExample:")
        print("  python amazon_reviews_scraper.py 'https://www.amazon.com/dp/B08N5WRWNW'")
        print("  python amazon_reviews_scraper.py 'https://www.amazon.com/dp/B08N5WRWNW' --max-pages 5 --output reviews.json")
        print("  python amazon_reviews_scraper.py 'https://www.amazon.com/dp/B08N5WRWNW' --debug")
        print("\nNote: Paste your Amazon product URL as the first argument")
        sys.exit(1)

    # Parse arguments
    product_url = sys.argv[1]
    max_pages = None
    output_file = 'amazon_reviews.json'
    delay_range = (2, 5)
    debug = False

    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--max-pages' and i + 1 < len(sys.argv):
            max_pages = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == '--output' and i + 1 < len(sys.argv):
            output_file = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--delay' and i + 2 < len(sys.argv):
            delay_range = (float(sys.argv[i + 1]), float(sys.argv[i + 2]))
            i += 3
        elif sys.argv[i] == '--debug':
            debug = True
            i += 1
        else:
            i += 1

    print("=" * 60)
    print("Amazon Reviews Scraper")
    print("=" * 60)
    print()

    try:
        # Create scraper instance
        scraper = AmazonReviewsScraper(product_url, debug=debug)

        # Scrape reviews
        output_data = scraper.scrape_reviews(max_pages=max_pages, delay_range=delay_range)

        # Save to JSON
        scraper.save_to_json(output_data, output_file)

        print(f"\n✓ Success! {len(output_data['reviews'])} reviews saved to {output_file}")

    except ValueError as e:
        print(f"\n⚠ Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user.")
        print(f"Partial data scraped: {len(scraper.reviews) if 'scraper' in locals() else 0} reviews")

        if 'scraper' in locals() and scraper.reviews:
            save_partial = input("Save partial results? (y/n): ").strip().lower()
            if save_partial == 'y':
                output_data = {
                    'product_asin': scraper.asin,
                    'product_title': scraper.product_title,
                    'product_url': scraper.product_url,
                    'total_reviews': len(scraper.reviews),
                    'scrape_date': datetime.now().isoformat(),
                    'reviews': scraper.reviews,
                    'note': 'Partial scrape - interrupted by user'
                }
                scraper.save_to_json(output_data, output_file)
        sys.exit(0)
    except Exception as e:
        print(f"\n⚠ Unexpected error: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
