"""
Amazon Product Review Scraper

Scrapes product reviews from Amazon product pages.
Handles pagination and extracts comprehensive review metadata.

Usage:
    python amazon_scraper.py --url "https://www.amazon.com/dp/PRODUCT_ID"
    python amazon_scraper.py --url "https://www.amazon.com/dp/PRODUCT_ID" --max-pages 5
"""

import argparse
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
import re
from urllib.parse import urljoin, urlparse, parse_qs
from .utils import (
    get_headers, delay, save_to_json, create_output_structure,
    RateLimitError, ScraperError, normalize_timestamp
)


class AmazonReviewScraper:
    """Scraper for Amazon product reviews."""

    BASE_DOMAIN = "https://www.amazon.com"

    def __init__(self, product_url: str, max_pages: int = 10):
        """
        Initialize Amazon scraper.

        Args:
            product_url: Amazon product URL (e.g., https://www.amazon.com/dp/B0XXXXX)
            max_pages: Maximum number of review pages to scrape
        """
        self.product_url = product_url
        self.max_pages = max_pages
        self.session = requests.Session()
        self.product_id = self._extract_product_id(product_url)

    def _extract_product_id(self, url: str) -> str:
        """Extract ASIN/product ID from Amazon URL."""
        patterns = [
            r'/dp/([A-Z0-9]{10})',
            r'/gp/product/([A-Z0-9]{10})',
            r'/product/([A-Z0-9]{10})',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        raise ValueError(f"Could not extract product ID from URL: {url}")

    def _get_reviews_url(self, page_number: int = 1) -> str:
        """
        Generate URL for reviews page.

        Args:
            page_number: Page number to fetch

        Returns:
            Reviews page URL
        """
        base_url = f"{self.BASE_DOMAIN}/product-reviews/{self.product_id}"
        if page_number > 1:
            return f"{base_url}?pageNumber={page_number}"
        return base_url

    def _parse_review_element(self, review_div) -> Optional[Dict[str, Any]]:
        """
        Parse a single review element from the page.

        Args:
            review_div: BeautifulSoup element containing review data

        Returns:
            Dictionary containing review data or None if parsing fails
        """
        try:
            review_data = {}

            # Review ID
            review_data['id'] = review_div.get('id', '')

            # Review text
            text_elem = review_div.find('span', {'data-hook': 'review-body'})
            review_data['text'] = text_elem.get_text(strip=True) if text_elem else ""

            # Author
            author_elem = review_div.find('span', class_='a-profile-name')
            review_data['author'] = author_elem.get_text(strip=True) if author_elem else "Anonymous"

            # Timestamp
            date_elem = review_div.find('span', {'data-hook': 'review-date'})
            if date_elem:
                date_text = date_elem.get_text(strip=True)
                # Extract date from "Reviewed in ... on Month Day, Year"
                date_match = re.search(r'on (.+)$', date_text)
                review_data['timestamp'] = date_match.group(1) if date_match else date_text
            else:
                review_data['timestamp'] = None

            # Rating (stars)
            rating_elem = review_div.find('i', {'data-hook': 'review-star-rating'})
            if rating_elem:
                rating_text = rating_elem.get_text(strip=True)
                rating_match = re.search(r'(\d+\.?\d*)', rating_text)
                review_data['rating'] = float(rating_match.group(1)) if rating_match else None
            else:
                review_data['rating'] = None

            # Helpful votes (likes)
            helpful_elem = review_div.find('span', {'data-hook': 'helpful-vote-statement'})
            if helpful_elem:
                helpful_text = helpful_elem.get_text(strip=True)
                helpful_match = re.search(r'(\d+)', helpful_text)
                review_data['likes'] = int(helpful_match.group(1)) if helpful_match else 0
            else:
                review_data['likes'] = 0

            # Review title
            title_elem = review_div.find('a', {'data-hook': 'review-title'})
            review_title = title_elem.get_text(strip=True) if title_elem else ""

            # Verified purchase
            verified_elem = review_div.find('span', {'data-hook': 'avp-badge'})
            verified_purchase = verified_elem is not None

            # Images attached to review
            image_elems = review_div.find_all('img', class_='review-image-tile')
            image_urls = [img.get('src', '') for img in image_elems if img.get('src')]

            # Profile link
            profile_elem = review_div.find('a', class_='a-profile')
            profile_link = urljoin(self.BASE_DOMAIN, profile_elem.get('href', '')) if profile_elem else None

            # Additional metadata
            review_data['replies'] = 0  # Amazon doesn't show reply count directly
            review_data['profile_link'] = profile_link
            review_data['verified_status'] = verified_purchase
            review_data['metadata'] = {
                'review_title': review_title,
                'verified_purchase': verified_purchase,
                'image_urls': image_urls,
                'review_url': f"{self.BASE_DOMAIN}/gp/customer-reviews/{review_data['id']}" if review_data['id'] else None,
            }

            return review_data

        except Exception as e:
            print(f"Error parsing review: {e}")
            return None

    def scrape_page(self, page_number: int = 1) -> List[Dict[str, Any]]:
        """
        Scrape reviews from a single page.

        Args:
            page_number: Page number to scrape

        Returns:
            List of review dictionaries
        """
        url = self._get_reviews_url(page_number)
        print(f"Scraping page {page_number}: {url}")

        try:
            response = self.session.get(url, headers=get_headers(), timeout=30)
            response.raise_for_status()

            # Check for CAPTCHA or access denied
            if "api-services-support@amazon.com" in response.text or "Robot Check" in response.text:
                raise RateLimitError("Amazon has detected automated access. Consider using proxies or reducing request rate.")

            soup = BeautifulSoup(response.content, 'html.parser')

            # Find all review divs
            review_divs = soup.find_all('div', {'data-hook': 'review'})

            if not review_divs:
                print(f"No reviews found on page {page_number}")
                return []

            reviews = []
            for review_div in review_divs:
                review_data = self._parse_review_element(review_div)
                if review_data:
                    reviews.append(review_data)

            print(f"Found {len(reviews)} reviews on page {page_number}")
            return reviews

        except requests.exceptions.RequestException as e:
            print(f"Error fetching page {page_number}: {e}")
            raise ScraperError(f"Failed to fetch page: {e}")

    def scrape_all_reviews(self) -> List[Dict[str, Any]]:
        """
        Scrape all reviews up to max_pages.

        Returns:
            List of all review dictionaries
        """
        all_reviews = []

        for page in range(1, self.max_pages + 1):
            try:
                reviews = self.scrape_page(page)

                if not reviews:
                    print(f"No more reviews found. Stopping at page {page}")
                    break

                all_reviews.extend(reviews)

                # Delay between pages to avoid rate limiting
                if page < self.max_pages:
                    delay(2, 4)

            except RateLimitError as e:
                print(f"Rate limit hit: {e}")
                break
            except ScraperError as e:
                print(f"Error on page {page}: {e}")
                break

        return all_reviews

    def scrape(self) -> Dict[str, Any]:
        """
        Main scraping method that returns standardized output.

        Returns:
            Dictionary with standardized structure
        """
        print(f"Starting Amazon review scraper for product: {self.product_id}")

        reviews = self.scrape_all_reviews()

        output = create_output_structure(
            platform="amazon",
            product_query=self.product_url,
            comments=reviews,
            additional_data={
                "product_id": self.product_id,
                "pages_scraped": min(len(reviews) // 10 + 1, self.max_pages) if reviews else 0,
            }
        )

        return output


def main():
    """Command-line interface for Amazon scraper."""
    parser = argparse.ArgumentParser(description="Scrape Amazon product reviews")
    parser.add_argument('--url', required=True, help='Amazon product URL')
    parser.add_argument('--max-pages', type=int, default=10, help='Maximum number of pages to scrape')
    parser.add_argument('--output', default='amazon_reviews.json', help='Output JSON file')

    args = parser.parse_args()

    try:
        scraper = AmazonReviewScraper(args.url, max_pages=args.max_pages)
        data = scraper.scrape()
        save_to_json(data, args.output)
        print(f"\nSuccessfully scraped {data['total_results']} reviews!")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
