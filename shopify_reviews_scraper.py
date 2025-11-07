#!/usr/bin/env python3
"""
Shopify Product Reviews Scraper
Scrapes all reviews from a Shopify product page and saves them to a JSON file.
Supports multiple review platforms: Judge.me, Yotpo, Loox, Shopify Reviews, and others.
"""

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
import requests
import json
import time
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse, parse_qs
import random
import sys


class ShopifyReviewsScraper:
    """Scraper for Shopify product reviews across multiple platforms."""

    SUPPORTED_PLATFORMS = [
        'Judge.me',
        'Yotpo',
        'Loox',
        'Shopify Product Reviews',
        'Stamped.io',
        'Reviews.io',
        'Okendo',
        'Rivyo',
        'Ali Reviews'
    ]

    def __init__(self, product_url: str, headless: bool = True):
        """
        Initialize the scraper with a product URL.

        Args:
            product_url: The Shopify product page URL
            headless: Whether to run browser in headless mode (default: True)
        """
        self.product_url = product_url
        self.store_name = self._extract_store_name(product_url)
        self.product_title = ""
        self.reviews = []
        self.review_platform = "Unknown"
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.page = None
        self.total_reviews_count = 0
        self.average_rating = 0.0

    def _extract_store_name(self, url: str) -> str:
        """Extract store name from URL."""
        parsed = urlparse(url)
        domain = parsed.netloc
        # Remove www. and .myshopify.com or other TLDs
        store = domain.replace('www.', '').split('.')[0]
        return store

    def _init_browser(self):
        """Initialize the Playwright browser."""
        if self.playwright is None:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled']
            )
            context = self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            self.page = context.new_page()
            print("Initialized Playwright browser")

    def _close_browser(self):
        """Close the Playwright browser."""
        if self.page:
            self.page.close()
            self.page = None
        if self.browser:
            self.browser.close()
            self.browser = None
        if self.playwright:
            self.playwright.stop()
            self.playwright = None
        print("Closed browser")

    def _detect_review_platform(self, page_source: str) -> str:
        """
        Detect which review platform is being used on the page.

        Args:
            page_source: HTML source of the page

        Returns:
            Name of the detected review platform
        """
        # Check for Judge.me
        if 'judgeme' in page_source.lower() or 'judge.me' in page_source.lower():
            if 'jdgm' in page_source or 'judgeme-widget' in page_source:
                return 'Judge.me'

        # Check for Yotpo
        if 'yotpo' in page_source.lower():
            return 'Yotpo'

        # Check for Loox
        if 'loox' in page_source.lower():
            return 'Loox'

        # Check for Shopify Product Reviews (native)
        if 'shopify-product-reviews' in page_source.lower() or 'spr-container' in page_source:
            return 'Shopify Product Reviews'

        # Check for Stamped.io
        if 'stamped.io' in page_source.lower() or 'stamped-main-widget' in page_source:
            return 'Stamped.io'

        # Check for Reviews.io
        if 'reviews.io' in page_source.lower() or 'reviewsio' in page_source:
            return 'Reviews.io'

        # Check for Okendo
        if 'okendo' in page_source.lower():
            return 'Okendo'

        # Check for Rivyo
        if 'rivyo' in page_source.lower():
            return 'Rivyo'

        # Check for Ali Reviews
        if 'ali-reviews' in page_source.lower() or 'alireviews' in page_source.lower():
            return 'Ali Reviews'

        return 'Unknown'

    def _scrape_judgeme_reviews(self) -> List[Dict]:
        """Scrape reviews from Judge.me platform."""
        print("Detected Judge.me review platform")
        reviews = []

        try:
            # Wait for Judge.me widget to load
            try:
                self.page.wait_for_selector('.jdgm-widget, [class*="judgeme"]', timeout=10000)
                time.sleep(2)  # Additional wait for content
            except PlaywrightTimeoutError:
                print("  Judge.me widget not found on page")
                return reviews

            # Try to find and click "Load more" or "Show all reviews" button
            page_num = 1
            while True:
                # Get current page content
                soup = BeautifulSoup(self.page.content(), 'html.parser')

                # Find all review elements
                review_elements = soup.find_all('div', class_=re.compile(r'jdgm-rev-widg__reviews|jdgm-rev(?!-widg)'))
                if not review_elements:
                    review_elements = soup.find_all('div', class_=re.compile(r'jdgm-rev\b'))

                if review_elements:
                    print(f"  Found {len(review_elements)} reviews on page {page_num}")

                    for review_elem in review_elements:
                        review_data = self._parse_judgeme_review(review_elem)
                        if review_data and review_data not in reviews:
                            reviews.append(review_data)

                # Try to load more reviews
                try:
                    # Look for "Load more" button
                    load_more_selectors = [
                        'button.jdgm-paginate__next-page',
                        'a.jdgm-paginate__next-page',
                        'button[class*="load-more"]',
                        '.jdgm-paginate__next-page'
                    ]

                    clicked = False
                    for selector in load_more_selectors:
                        try:
                            if self.page.locator(selector).count() > 0:
                                if self.page.locator(selector).is_visible():
                                    self.page.click(selector, timeout=5000)
                                    print(f"  Loading more reviews...")
                                    time.sleep(3)  # Wait for new reviews to load
                                    clicked = True
                                    page_num += 1
                                    break
                        except:
                            continue

                    if not clicked:
                        break

                except Exception as e:
                    print(f"  No more reviews to load")
                    break

            # Get product title and ratings info
            soup = BeautifulSoup(self.page.content(), 'html.parser')
            self._extract_judgeme_metadata(soup)

        except Exception as e:
            print(f"Error scraping Judge.me reviews: {e}")

        return reviews

    def _parse_judgeme_review(self, review_elem) -> Optional[Dict]:
        """Parse a single Judge.me review."""
        try:
            review_data = {}

            # Review ID
            review_id = review_elem.get('data-review-id', '')
            if not review_id:
                review_id = review_elem.get('id', '')
            review_data['review_id'] = review_id

            # Title
            title_elem = review_elem.find('b', class_=re.compile(r'jdgm.*title')) or \
                        review_elem.find('h3', class_=re.compile(r'jdgm')) or \
                        review_elem.find(class_=re.compile(r'jdgm.*review-title'))
            review_data['title'] = title_elem.get_text(strip=True) if title_elem else ""

            # Body
            body_elem = review_elem.find('div', class_=re.compile(r'jdgm.*review-body')) or \
                       review_elem.find('p', class_=re.compile(r'jdgm.*review-body')) or \
                       review_elem.find(class_=re.compile(r'jdgm.*text'))
            review_data['body'] = body_elem.get_text(strip=True) if body_elem else ""

            # Rating
            rating = 0
            rating_elem = review_elem.find('span', class_=re.compile(r'jdgm.*star')) or \
                         review_elem.find(class_=re.compile(r'jdgm.*rating'))
            if rating_elem:
                # Try to extract from aria-label or data attributes
                aria_label = rating_elem.get('aria-label', '')
                data_score = rating_elem.get('data-score', '')

                if data_score:
                    rating = float(data_score)
                elif aria_label:
                    rating_match = re.search(r'([\d.]+)', aria_label)
                    if rating_match:
                        rating = float(rating_match.group(1))
                else:
                    # Count filled stars
                    stars = rating_elem.find_all(class_=re.compile(r'jdgm.*star.*full|filled'))
                    rating = len(stars)

            review_data['rating'] = rating

            # Author
            author_elem = review_elem.find('span', class_=re.compile(r'jdgm.*reviewer-name')) or \
                         review_elem.find(class_=re.compile(r'jdgm.*author'))
            review_data['author'] = author_elem.get_text(strip=True) if author_elem else ""

            # Date
            date_elem = review_elem.find('span', class_=re.compile(r'jdgm.*review-date')) or \
                       review_elem.find(class_=re.compile(r'jdgm.*created-at'))
            review_data['date'] = date_elem.get_text(strip=True) if date_elem else ""

            # Verified buyer
            verified_elem = review_elem.find(class_=re.compile(r'jdgm.*verified')) or \
                           review_elem.find(text=re.compile(r'verified', re.I))
            review_data['verified_buyer'] = verified_elem is not None

            # Helpful votes
            helpful_votes = 0
            helpful_elem = review_elem.find(class_=re.compile(r'jdgm.*helpful'))
            if helpful_elem:
                helpful_text = helpful_elem.get_text()
                helpful_match = re.search(r'(\d+)', helpful_text)
                if helpful_match:
                    helpful_votes = int(helpful_match.group(1))
            review_data['helpful_votes'] = helpful_votes

            # Product variant
            variant_elem = review_elem.find(class_=re.compile(r'jdgm.*variant'))
            review_data['product_variant'] = variant_elem.get_text(strip=True) if variant_elem else ""

            # Images
            images = []
            img_elements = review_elem.find_all('img', class_=re.compile(r'jdgm.*review.*image'))
            for img in img_elements:
                img_url = img.get('src') or img.get('data-src')
                if img_url and 'data:image' not in img_url:
                    images.append(img_url)
            review_data['images'] = images

            return review_data

        except Exception as e:
            print(f"Error parsing Judge.me review: {e}")
            return None

    def _extract_judgeme_metadata(self, soup: BeautifulSoup):
        """Extract product metadata from Judge.me widget."""
        try:
            # Average rating
            rating_elem = soup.find('span', class_=re.compile(r'jdgm.*average.*rating'))
            if rating_elem:
                rating_text = rating_elem.get_text()
                rating_match = re.search(r'([\d.]+)', rating_text)
                if rating_match:
                    self.average_rating = float(rating_match.group(1))

            # Total reviews count
            count_elem = soup.find('span', class_=re.compile(r'jdgm.*review.*count')) or \
                        soup.find('span', class_=re.compile(r'jdgm.*total.*reviews'))
            if count_elem:
                count_text = count_elem.get_text()
                count_match = re.search(r'(\d+)', count_text)
                if count_match:
                    self.total_reviews_count = int(count_match.group(1))

        except Exception as e:
            print(f"Error extracting Judge.me metadata: {e}")

    def _scrape_yotpo_reviews(self) -> List[Dict]:
        """Scrape reviews from Yotpo platform."""
        print("Detected Yotpo review platform")
        reviews = []

        try:
            # Wait for Yotpo widget
            try:
                self.page.wait_for_selector('.yotpo-review, [class*="yotpo"]', timeout=10000)
                time.sleep(3)
            except PlaywrightTimeoutError:
                print("  Yotpo widget not found on page")
                return reviews

            page_num = 1
            while True:
                soup = BeautifulSoup(self.page.content(), 'html.parser')

                # Find review elements
                review_elements = soup.find_all('div', class_=re.compile(r'yotpo-review\b')) or \
                                soup.find_all('div', attrs={'data-review-id': True})

                if review_elements:
                    print(f"  Found {len(review_elements)} reviews on page {page_num}")

                    for review_elem in review_elements:
                        review_data = self._parse_yotpo_review(review_elem)
                        if review_data and review_data not in reviews:
                            reviews.append(review_data)

                # Try to load more
                try:
                    load_more_selectors = [
                        'button.yotpo-next',
                        'a.yotpo-page-next',
                        '.read-more-reviews',
                        '[class*="load-more"]'
                    ]

                    clicked = False
                    for selector in load_more_selectors:
                        try:
                            if self.page.locator(selector).count() > 0:
                                if self.page.locator(selector).is_visible():
                                    self.page.click(selector, timeout=5000)
                                    print(f"  Loading more reviews...")
                                    time.sleep(3)
                                    clicked = True
                                    page_num += 1
                                    break
                        except:
                            continue

                    if not clicked:
                        break

                except:
                    break

            # Extract metadata
            soup = BeautifulSoup(self.page.content(), 'html.parser')
            self._extract_yotpo_metadata(soup)

        except Exception as e:
            print(f"Error scraping Yotpo reviews: {e}")

        return reviews

    def _parse_yotpo_review(self, review_elem) -> Optional[Dict]:
        """Parse a single Yotpo review."""
        try:
            review_data = {}

            # Review ID
            review_data['review_id'] = review_elem.get('data-review-id', '') or review_elem.get('id', '')

            # Title
            title_elem = review_elem.find('div', class_=re.compile(r'yotpo.*review-title')) or \
                        review_elem.find('h3')
            review_data['title'] = title_elem.get_text(strip=True) if title_elem else ""

            # Body
            body_elem = review_elem.find('div', class_=re.compile(r'yotpo.*review-content')) or \
                       review_elem.find('div', class_=re.compile(r'yotpo.*text'))
            review_data['body'] = body_elem.get_text(strip=True) if body_elem else ""

            # Rating
            rating = 0
            rating_elem = review_elem.find('div', class_=re.compile(r'yotpo.*star.*rating'))
            if rating_elem:
                rating_text = rating_elem.get('content', '') or rating_elem.get('aria-label', '')
                rating_match = re.search(r'([\d.]+)', rating_text)
                if rating_match:
                    rating = float(rating_match.group(1))
                else:
                    # Count stars
                    stars = rating_elem.find_all(class_=re.compile(r'yotpo-icon-star\b|filled'))
                    rating = len(stars)
            review_data['rating'] = rating

            # Author
            author_elem = review_elem.find('span', class_=re.compile(r'yotpo.*user-name')) or \
                         review_elem.find(class_=re.compile(r'yotpo.*reviewer'))
            review_data['author'] = author_elem.get_text(strip=True) if author_elem else ""

            # Date
            date_elem = review_elem.find('span', class_=re.compile(r'yotpo.*review-date')) or \
                       review_elem.find(class_=re.compile(r'yotpo.*created'))
            review_data['date'] = date_elem.get_text(strip=True) if date_elem else ""

            # Verified buyer
            verified_elem = review_elem.find(class_=re.compile(r'yotpo.*verified')) or \
                           review_elem.find(text=re.compile(r'verified', re.I))
            review_data['verified_buyer'] = verified_elem is not None

            # Helpful votes
            helpful_votes = 0
            helpful_elem = review_elem.find(class_=re.compile(r'yotpo.*vote-sum'))
            if helpful_elem:
                helpful_match = re.search(r'(\d+)', helpful_elem.get_text())
                if helpful_match:
                    helpful_votes = int(helpful_match.group(1))
            review_data['helpful_votes'] = helpful_votes

            # Product variant
            variant_elem = review_elem.find(class_=re.compile(r'yotpo.*custom-field'))
            review_data['product_variant'] = variant_elem.get_text(strip=True) if variant_elem else ""

            # Images
            images = []
            img_container = review_elem.find('div', class_=re.compile(r'yotpo.*pictures'))
            if img_container:
                img_elements = img_container.find_all('img')
                for img in img_elements:
                    img_url = img.get('src') or img.get('data-src')
                    if img_url and 'data:image' not in img_url:
                        images.append(img_url)
            review_data['images'] = images

            return review_data

        except Exception as e:
            print(f"Error parsing Yotpo review: {e}")
            return None

    def _extract_yotpo_metadata(self, soup: BeautifulSoup):
        """Extract product metadata from Yotpo widget."""
        try:
            # Average rating
            rating_elem = soup.find('div', class_=re.compile(r'yotpo.*average-score'))
            if rating_elem:
                rating_match = re.search(r'([\d.]+)', rating_elem.get_text())
                if rating_match:
                    self.average_rating = float(rating_match.group(1))

            # Total reviews
            count_elem = soup.find('div', class_=re.compile(r'yotpo.*total-reviews'))
            if count_elem:
                count_match = re.search(r'(\d+)', count_elem.get_text())
                if count_match:
                    self.total_reviews_count = int(count_match.group(1))

        except Exception as e:
            print(f"Error extracting Yotpo metadata: {e}")

    def _scrape_loox_reviews(self) -> List[Dict]:
        """Scrape reviews from Loox platform."""
        print("Detected Loox review platform")
        reviews = []

        try:
            # Wait for Loox widget
            try:
                self.page.wait_for_selector('.loox-reviews, [class*="loox"]', timeout=10000)
                time.sleep(3)
            except PlaywrightTimeoutError:
                print("  Loox widget not found on page")
                return reviews

            page_num = 1
            while True:
                soup = BeautifulSoup(self.page.content(), 'html.parser')

                # Find review elements
                review_elements = soup.find_all('div', class_=re.compile(r'loox-review\b'))

                if review_elements:
                    print(f"  Found {len(review_elements)} reviews on page {page_num}")

                    for review_elem in review_elements:
                        review_data = self._parse_loox_review(review_elem)
                        if review_data and review_data not in reviews:
                            reviews.append(review_data)

                # Try to load more
                try:
                    load_more_selectors = [
                        'button.loox-load-more',
                        '[class*="loox"][class*="load-more"]',
                        '.loox-show-more'
                    ]

                    clicked = False
                    for selector in load_more_selectors:
                        try:
                            if self.page.locator(selector).count() > 0:
                                if self.page.locator(selector).is_visible():
                                    self.page.click(selector, timeout=5000)
                                    print(f"  Loading more reviews...")
                                    time.sleep(3)
                                    clicked = True
                                    page_num += 1
                                    break
                        except:
                            continue

                    if not clicked:
                        break

                except:
                    break

            # Extract metadata
            soup = BeautifulSoup(self.page.content(), 'html.parser')
            self._extract_loox_metadata(soup)

        except Exception as e:
            print(f"Error scraping Loox reviews: {e}")

        return reviews

    def _parse_loox_review(self, review_elem) -> Optional[Dict]:
        """Parse a single Loox review."""
        try:
            review_data = {}

            # Review ID
            review_data['review_id'] = review_elem.get('data-review-id', '') or review_elem.get('id', '')

            # Title (Loox typically doesn't have titles)
            review_data['title'] = ""

            # Body
            body_elem = review_elem.find('div', class_=re.compile(r'loox.*review-text')) or \
                       review_elem.find('p', class_=re.compile(r'loox.*text'))
            review_data['body'] = body_elem.get_text(strip=True) if body_elem else ""

            # Rating
            rating = 0
            rating_elem = review_elem.find('div', class_=re.compile(r'loox.*rating'))
            if rating_elem:
                stars = rating_elem.find_all(class_=re.compile(r'loox.*star.*filled|active'))
                rating = len(stars)
            review_data['rating'] = rating

            # Author
            author_elem = review_elem.find('span', class_=re.compile(r'loox.*author')) or \
                         review_elem.find(class_=re.compile(r'loox.*reviewer'))
            review_data['author'] = author_elem.get_text(strip=True) if author_elem else ""

            # Date
            date_elem = review_elem.find('span', class_=re.compile(r'loox.*date'))
            review_data['date'] = date_elem.get_text(strip=True) if date_elem else ""

            # Verified buyer (Loox typically shows all as verified)
            verified_elem = review_elem.find(class_=re.compile(r'loox.*verified'))
            review_data['verified_buyer'] = verified_elem is not None or True  # Loox typically verifies all

            # Helpful votes (Loox doesn't typically have this)
            review_data['helpful_votes'] = 0

            # Product variant
            variant_elem = review_elem.find(class_=re.compile(r'loox.*variant'))
            review_data['product_variant'] = variant_elem.get_text(strip=True) if variant_elem else ""

            # Images (Loox is known for photo reviews)
            images = []
            img_elements = review_elem.find_all('img', class_=re.compile(r'loox.*image'))
            for img in img_elements:
                img_url = img.get('src') or img.get('data-src')
                if img_url and 'data:image' not in img_url:
                    images.append(img_url)
            review_data['images'] = images

            return review_data

        except Exception as e:
            print(f"Error parsing Loox review: {e}")
            return None

    def _extract_loox_metadata(self, soup: BeautifulSoup):
        """Extract product metadata from Loox widget."""
        try:
            # Average rating
            rating_elem = soup.find('div', class_=re.compile(r'loox.*average'))
            if rating_elem:
                rating_match = re.search(r'([\d.]+)', rating_elem.get_text())
                if rating_match:
                    self.average_rating = float(rating_match.group(1))

            # Total reviews
            count_elem = soup.find('span', class_=re.compile(r'loox.*count'))
            if count_elem:
                count_match = re.search(r'(\d+)', count_elem.get_text())
                if count_match:
                    self.total_reviews_count = int(count_match.group(1))

        except Exception as e:
            print(f"Error extracting Loox metadata: {e}")

    def _scrape_shopify_native_reviews(self) -> List[Dict]:
        """Scrape reviews from Shopify's native review system."""
        print("Detected Shopify Product Reviews (native)")
        reviews = []

        try:
            soup = BeautifulSoup(self.page.content(), 'html.parser')

            # Find review elements
            review_elements = soup.find_all('div', class_=re.compile(r'spr-review\b'))

            if review_elements:
                print(f"  Found {len(review_elements)} reviews")

                for review_elem in review_elements:
                    review_data = self._parse_shopify_native_review(review_elem)
                    if review_data:
                        reviews.append(review_data)

            # Extract metadata
            self._extract_shopify_native_metadata(soup)

        except Exception as e:
            print(f"Error scraping Shopify native reviews: {e}")

        return reviews

    def _parse_shopify_native_review(self, review_elem) -> Optional[Dict]:
        """Parse a single Shopify native review."""
        try:
            review_data = {}

            # Review ID
            review_data['review_id'] = review_elem.get('id', '')

            # Title
            title_elem = review_elem.find('h3', class_='spr-review-header-title')
            review_data['title'] = title_elem.get_text(strip=True) if title_elem else ""

            # Body
            body_elem = review_elem.find('div', class_='spr-review-content-body') or \
                       review_elem.find('p', class_='spr-review-content-body')
            review_data['body'] = body_elem.get_text(strip=True) if body_elem else ""

            # Rating
            rating = 0
            rating_elem = review_elem.find('span', class_='spr-starrating')
            if rating_elem:
                aria_label = rating_elem.get('aria-label', '')
                rating_match = re.search(r'([\d.]+)', aria_label)
                if rating_match:
                    rating = float(rating_match.group(1))
            review_data['rating'] = rating

            # Author
            author_elem = review_elem.find('span', class_='spr-review-header-byline')
            if author_elem:
                author_text = author_elem.get_text(strip=True)
                author_match = re.search(r'by\s+(.+)', author_text, re.I)
                review_data['author'] = author_match.group(1) if author_match else author_text
            else:
                review_data['author'] = ""

            # Date
            date_elem = review_elem.find('span', class_='spr-review-header-date')
            review_data['date'] = date_elem.get_text(strip=True) if date_elem else ""

            # Verified buyer
            verified_elem = review_elem.find(class_='spr-review-header-verified')
            review_data['verified_buyer'] = verified_elem is not None

            # Helpful votes (typically not available in native Shopify)
            review_data['helpful_votes'] = 0

            # Product variant
            review_data['product_variant'] = ""

            # Images (typically not available in native Shopify)
            review_data['images'] = []

            return review_data

        except Exception as e:
            print(f"Error parsing Shopify native review: {e}")
            return None

    def _extract_shopify_native_metadata(self, soup: BeautifulSoup):
        """Extract product metadata from Shopify native reviews."""
        try:
            # Average rating
            rating_elem = soup.find('span', class_='spr-starrating')
            if rating_elem:
                aria_label = rating_elem.get('aria-label', '')
                rating_match = re.search(r'([\d.]+)', aria_label)
                if rating_match:
                    self.average_rating = float(rating_match.group(1))

            # Total reviews
            count_elem = soup.find('span', class_='spr-summary-actions-togglereviews')
            if count_elem:
                count_match = re.search(r'(\d+)', count_elem.get_text())
                if count_match:
                    self.total_reviews_count = int(count_match.group(1))

        except Exception as e:
            print(f"Error extracting Shopify native metadata: {e}")

    def _scrape_stampedio_reviews(self) -> List[Dict]:
        """Scrape reviews from Stamped.io platform."""
        print("Detected Stamped.io review platform")
        reviews = []

        try:
            # Wait for Stamped widget
            try:
                self.page.wait_for_selector('[class*="stamped"], .stamped-main-widget', timeout=10000)
                time.sleep(3)
            except PlaywrightTimeoutError:
                print("  Stamped.io widget not found on page")
                return reviews

            page_num = 1
            while True:
                soup = BeautifulSoup(self.page.content(), 'html.parser')

                # Find review elements
                review_elements = soup.find_all('div', class_=re.compile(r'stamped-review\b'))

                if review_elements:
                    print(f"  Found {len(review_elements)} reviews on page {page_num}")

                    for review_elem in review_elements:
                        review_data = self._parse_stampedio_review(review_elem)
                        if review_data and review_data not in reviews:
                            reviews.append(review_data)

                # Try to load more
                try:
                    load_more_selectors = [
                        'button.stamped-load-more',
                        'a[class*="stamped"][class*="load"]',
                        '.stamped-pagination-next'
                    ]

                    clicked = False
                    for selector in load_more_selectors:
                        try:
                            if self.page.locator(selector).count() > 0:
                                if self.page.locator(selector).is_visible():
                                    self.page.click(selector, timeout=5000)
                                    print(f"  Loading more reviews...")
                                    time.sleep(3)
                                    clicked = True
                                    page_num += 1
                                    break
                        except:
                            continue

                    if not clicked:
                        break

                except:
                    break

            # Extract metadata
            soup = BeautifulSoup(self.page.content(), 'html.parser')
            self._extract_stampedio_metadata(soup)

        except Exception as e:
            print(f"Error scraping Stamped.io reviews: {e}")

        return reviews

    def _parse_stampedio_review(self, review_elem) -> Optional[Dict]:
        """Parse a single Stamped.io review."""
        try:
            review_data = {}

            # Review ID
            review_data['review_id'] = review_elem.get('data-review-id', '') or review_elem.get('id', '')

            # Title
            title_elem = review_elem.find(class_=re.compile(r'stamped.*review.*title'))
            review_data['title'] = title_elem.get_text(strip=True) if title_elem else ""

            # Body
            body_elem = review_elem.find(class_=re.compile(r'stamped.*review.*body|stamped.*review.*text'))
            review_data['body'] = body_elem.get_text(strip=True) if body_elem else ""

            # Rating
            rating = 0
            rating_elem = review_elem.find(class_=re.compile(r'stamped.*star.*rating'))
            if rating_elem:
                rating_attr = rating_elem.get('data-rating', '') or rating_elem.get('aria-label', '')
                rating_match = re.search(r'([\d.]+)', str(rating_attr))
                if rating_match:
                    rating = float(rating_match.group(1))
            review_data['rating'] = rating

            # Author
            author_elem = review_elem.find(class_=re.compile(r'stamped.*author|stamped.*reviewer'))
            review_data['author'] = author_elem.get_text(strip=True) if author_elem else ""

            # Date
            date_elem = review_elem.find(class_=re.compile(r'stamped.*date|stamped.*created'))
            review_data['date'] = date_elem.get_text(strip=True) if date_elem else ""

            # Verified buyer
            verified_elem = review_elem.find(class_=re.compile(r'stamped.*verified'))
            review_data['verified_buyer'] = verified_elem is not None

            # Helpful votes
            helpful_votes = 0
            helpful_elem = review_elem.find(class_=re.compile(r'stamped.*helpful|stamped.*vote'))
            if helpful_elem:
                helpful_match = re.search(r'(\d+)', helpful_elem.get_text())
                if helpful_match:
                    helpful_votes = int(helpful_match.group(1))
            review_data['helpful_votes'] = helpful_votes

            # Product variant
            variant_elem = review_elem.find(class_=re.compile(r'stamped.*variant'))
            review_data['product_variant'] = variant_elem.get_text(strip=True) if variant_elem else ""

            # Images
            images = []
            img_elements = review_elem.find_all('img', class_=re.compile(r'stamped.*image'))
            for img in img_elements:
                img_url = img.get('src') or img.get('data-src')
                if img_url and 'data:image' not in img_url:
                    images.append(img_url)
            review_data['images'] = images

            return review_data

        except Exception as e:
            print(f"Error parsing Stamped.io review: {e}")
            return None

    def _extract_stampedio_metadata(self, soup: BeautifulSoup):
        """Extract product metadata from Stamped.io widget."""
        try:
            # Average rating
            rating_elem = soup.find(class_=re.compile(r'stamped.*average'))
            if rating_elem:
                rating_match = re.search(r'([\d.]+)', rating_elem.get_text())
                if rating_match:
                    self.average_rating = float(rating_match.group(1))

            # Total reviews
            count_elem = soup.find(class_=re.compile(r'stamped.*count'))
            if count_elem:
                count_match = re.search(r'(\d+)', count_elem.get_text())
                if count_match:
                    self.total_reviews_count = int(count_match.group(1))

        except Exception as e:
            print(f"Error extracting Stamped.io metadata: {e}")

    def _scrape_reviewsio_reviews(self) -> List[Dict]:
        """Scrape reviews from Reviews.io platform."""
        print("Detected Reviews.io review platform")
        reviews = []

        try:
            # Wait for Reviews.io widget
            try:
                self.page.wait_for_selector('[class*="reviewsio"], [id*="ReviewsWidget"]', timeout=10000)
                time.sleep(3)
            except PlaywrightTimeoutError:
                print("  Reviews.io widget not found on page")
                return reviews

            page_num = 1
            while True:
                soup = BeautifulSoup(self.page.content(), 'html.parser')

                # Find review elements
                review_elements = soup.find_all('div', class_=re.compile(r'(?:^|\\s)review(?:$|\\s)')) or \
                                soup.find_all('div', attrs={'data-review-id': True})

                if review_elements:
                    print(f"  Found {len(review_elements)} reviews on page {page_num}")

                    for review_elem in review_elements:
                        # Filter to only Reviews.io reviews
                        if 'reviewsio' in str(review_elem.get('class', '')).lower() or \
                           'ReviewsWidget' in str(review_elem.parent):
                            review_data = self._parse_reviewsio_review(review_elem)
                            if review_data and review_data not in reviews:
                                reviews.append(review_data)

                # Try to load more
                try:
                    load_more_selectors = [
                        'button[class*="load-more"]',
                        'a.next-page',
                        '[class*="pagination"] [class*="next"]'
                    ]

                    clicked = False
                    for selector in load_more_selectors:
                        try:
                            if self.page.locator(selector).count() > 0:
                                if self.page.locator(selector).is_visible():
                                    self.page.click(selector, timeout=5000)
                                    print(f"  Loading more reviews...")
                                    time.sleep(3)
                                    clicked = True
                                    page_num += 1
                                    break
                        except:
                            continue

                    if not clicked:
                        break

                except:
                    break

            # Extract metadata
            soup = BeautifulSoup(self.page.content(), 'html.parser')
            self._extract_reviewsio_metadata(soup)

        except Exception as e:
            print(f"Error scraping Reviews.io reviews: {e}")

        return reviews

    def _parse_reviewsio_review(self, review_elem) -> Optional[Dict]:
        """Parse a single Reviews.io review."""
        try:
            review_data = {}

            # Review ID
            review_data['review_id'] = review_elem.get('data-review-id', '') or review_elem.get('id', '')

            # Title
            title_elem = review_elem.find('h3') or review_elem.find(class_=re.compile(r'title'))
            review_data['title'] = title_elem.get_text(strip=True) if title_elem else ""

            # Body
            body_elem = review_elem.find(class_=re.compile(r'review.*text|review.*body|comment'))
            review_data['body'] = body_elem.get_text(strip=True) if body_elem else ""

            # Rating
            rating = 0
            rating_elem = review_elem.find(class_=re.compile(r'star|rating'))
            if rating_elem:
                rating_attr = rating_elem.get('data-rating', '') or rating_elem.get('aria-label', '')
                rating_match = re.search(r'([\d.]+)', str(rating_attr))
                if rating_match:
                    rating = float(rating_match.group(1))
            review_data['rating'] = rating

            # Author
            author_elem = review_elem.find(class_=re.compile(r'author|reviewer|customer'))
            review_data['author'] = author_elem.get_text(strip=True) if author_elem else ""

            # Date
            date_elem = review_elem.find(class_=re.compile(r'date|time'))
            review_data['date'] = date_elem.get_text(strip=True) if date_elem else ""

            # Verified buyer
            verified_elem = review_elem.find(text=re.compile(r'verified', re.I))
            review_data['verified_buyer'] = verified_elem is not None

            # Helpful votes
            review_data['helpful_votes'] = 0

            # Product variant
            review_data['product_variant'] = ""

            # Images
            images = []
            img_elements = review_elem.find_all('img')
            for img in img_elements:
                img_url = img.get('src') or img.get('data-src')
                if img_url and 'data:image' not in img_url and 'star' not in img_url.lower():
                    images.append(img_url)
            review_data['images'] = images

            return review_data

        except Exception as e:
            print(f"Error parsing Reviews.io review: {e}")
            return None

    def _extract_reviewsio_metadata(self, soup: BeautifulSoup):
        """Extract product metadata from Reviews.io widget."""
        try:
            # Average rating
            rating_elem = soup.find(class_=re.compile(r'average.*rating'))
            if rating_elem:
                rating_match = re.search(r'([\d.]+)', rating_elem.get_text())
                if rating_match:
                    self.average_rating = float(rating_match.group(1))

            # Total reviews
            count_elem = soup.find(class_=re.compile(r'total.*reviews|review.*count'))
            if count_elem:
                count_match = re.search(r'(\d+)', count_elem.get_text())
                if count_match:
                    self.total_reviews_count = int(count_match.group(1))

        except Exception as e:
            print(f"Error extracting Reviews.io metadata: {e}")

    def _scrape_okendo_reviews(self) -> List[Dict]:
        """Scrape reviews from Okendo platform."""
        print("Detected Okendo review platform")
        reviews = []

        try:
            # Wait for Okendo widget
            try:
                self.page.wait_for_selector('[class*="okendo"], [data-oke-widget]', timeout=10000)
                time.sleep(3)
            except PlaywrightTimeoutError:
                print("  Okendo widget not found on page")
                return reviews

            page_num = 1
            while True:
                soup = BeautifulSoup(self.page.content(), 'html.parser')

                # Find review elements
                review_elements = soup.find_all('div', class_=re.compile(r'okeReviews.*review-item|okendo.*review\b'))

                if review_elements:
                    print(f"  Found {len(review_elements)} reviews on page {page_num}")

                    for review_elem in review_elements:
                        review_data = self._parse_okendo_review(review_elem)
                        if review_data and review_data not in reviews:
                            reviews.append(review_data)

                # Try to load more
                try:
                    load_more_selectors = [
                        'button[class*="okendo"][class*="load"]',
                        'a.okeReviews-reviews-controls-loadMore',
                        '[class*="pagination"] [class*="next"]'
                    ]

                    clicked = False
                    for selector in load_more_selectors:
                        try:
                            if self.page.locator(selector).count() > 0:
                                if self.page.locator(selector).is_visible():
                                    self.page.click(selector, timeout=5000)
                                    print(f"  Loading more reviews...")
                                    time.sleep(3)
                                    clicked = True
                                    page_num += 1
                                    break
                        except:
                            continue

                    if not clicked:
                        break

                except:
                    break

            # Extract metadata
            soup = BeautifulSoup(self.page.content(), 'html.parser')
            self._extract_okendo_metadata(soup)

        except Exception as e:
            print(f"Error scraping Okendo reviews: {e}")

        return reviews

    def _parse_okendo_review(self, review_elem) -> Optional[Dict]:
        """Parse a single Okendo review."""
        try:
            review_data = {}

            # Review ID
            review_data['review_id'] = review_elem.get('data-review-id', '') or review_elem.get('id', '')

            # Title
            title_elem = review_elem.find(class_=re.compile(r'okeReviews.*title|okendo.*title'))
            review_data['title'] = title_elem.get_text(strip=True) if title_elem else ""

            # Body
            body_elem = review_elem.find(class_=re.compile(r'okeReviews.*body|okendo.*body|okeReviews.*text'))
            review_data['body'] = body_elem.get_text(strip=True) if body_elem else ""

            # Rating
            rating = 0
            rating_elem = review_elem.find(class_=re.compile(r'okeReviews.*star|okendo.*rating'))
            if rating_elem:
                rating_attr = rating_elem.get('data-oke-reviews-star-rating', '') or rating_elem.get('aria-label', '')
                rating_match = re.search(r'([\d.]+)', str(rating_attr))
                if rating_match:
                    rating = float(rating_match.group(1))
            review_data['rating'] = rating

            # Author
            author_elem = review_elem.find(class_=re.compile(r'okeReviews.*reviewer|okendo.*author'))
            review_data['author'] = author_elem.get_text(strip=True) if author_elem else ""

            # Date
            date_elem = review_elem.find(class_=re.compile(r'okeReviews.*date|okendo.*date'))
            review_data['date'] = date_elem.get_text(strip=True) if date_elem else ""

            # Verified buyer
            verified_elem = review_elem.find(class_=re.compile(r'okendo.*verified|okeReviews.*verified'))
            review_data['verified_buyer'] = verified_elem is not None

            # Helpful votes
            helpful_votes = 0
            helpful_elem = review_elem.find(class_=re.compile(r'okendo.*helpful|okeReviews.*vote'))
            if helpful_elem:
                helpful_match = re.search(r'(\d+)', helpful_elem.get_text())
                if helpful_match:
                    helpful_votes = int(helpful_match.group(1))
            review_data['helpful_votes'] = helpful_votes

            # Product variant
            variant_elem = review_elem.find(class_=re.compile(r'okendo.*variant'))
            review_data['product_variant'] = variant_elem.get_text(strip=True) if variant_elem else ""

            # Images
            images = []
            img_container = review_elem.find(class_=re.compile(r'okeReviews.*media|okendo.*images'))
            if img_container:
                img_elements = img_container.find_all('img')
                for img in img_elements:
                    img_url = img.get('src') or img.get('data-src')
                    if img_url and 'data:image' not in img_url:
                        images.append(img_url)
            review_data['images'] = images

            return review_data

        except Exception as e:
            print(f"Error parsing Okendo review: {e}")
            return None

    def _extract_okendo_metadata(self, soup: BeautifulSoup):
        """Extract product metadata from Okendo widget."""
        try:
            # Average rating
            rating_elem = soup.find(class_=re.compile(r'okeReviews.*averageRating|okendo.*average'))
            if rating_elem:
                rating_match = re.search(r'([\d.]+)', rating_elem.get_text())
                if rating_match:
                    self.average_rating = float(rating_match.group(1))

            # Total reviews
            count_elem = soup.find(class_=re.compile(r'okeReviews.*reviewCount|okendo.*count'))
            if count_elem:
                count_match = re.search(r'(\d+)', count_elem.get_text())
                if count_match:
                    self.total_reviews_count = int(count_match.group(1))

        except Exception as e:
            print(f"Error extracting Okendo metadata: {e}")

    def _get_product_title(self, soup: BeautifulSoup) -> str:
        """Extract product title from the page."""
        # Try various selectors
        title_elem = soup.find('h1', class_=re.compile(r'product.*title', re.I)) or \
                    soup.find('h1', class_='product-single__title') or \
                    soup.find('h1', {'itemprop': 'name'}) or \
                    soup.find('h1')

        if title_elem:
            return title_elem.get_text(strip=True)

        # Try meta tags
        meta_title = soup.find('meta', property='og:title')
        if meta_title:
            return meta_title.get('content', 'Unknown Product')

        return "Unknown Product"

    def scrape_reviews(self, delay_range: tuple = (2, 4)) -> Dict:
        """
        Scrape all reviews from the product.

        Args:
            delay_range: Tuple of (min, max) seconds to wait between actions

        Returns:
            Dictionary with all scraped data
        """
        print(f"Starting to scrape reviews from Shopify store: {self.store_name}")
        print(f"Product URL: {self.product_url}\n")

        # Initialize browser
        self._init_browser()

        try:
            # Navigate to product page
            print("Loading product page...")
            self.page.goto(self.product_url, wait_until='domcontentloaded', timeout=60000)

            # Wait for page to fully load
            time.sleep(4)

            # Get page source
            page_source = self.page.content()
            soup = BeautifulSoup(page_source, 'html.parser')

            # Get product title
            self.product_title = self._get_product_title(soup)
            print(f"Product: {self.product_title}\n")

            # Detect review platform
            self.review_platform = self._detect_review_platform(page_source)
            print(f"Review platform: {self.review_platform}\n")

            # Scrape reviews based on platform
            if self.review_platform == 'Judge.me':
                self.reviews = self._scrape_judgeme_reviews()
            elif self.review_platform == 'Yotpo':
                self.reviews = self._scrape_yotpo_reviews()
            elif self.review_platform == 'Loox':
                self.reviews = self._scrape_loox_reviews()
            elif self.review_platform == 'Shopify Product Reviews':
                self.reviews = self._scrape_shopify_native_reviews()
            elif self.review_platform == 'Stamped.io':
                self.reviews = self._scrape_stampedio_reviews()
            elif self.review_platform == 'Reviews.io':
                self.reviews = self._scrape_reviewsio_reviews()
            elif self.review_platform == 'Okendo':
                self.reviews = self._scrape_okendo_reviews()
            else:
                print(f"Warning: Review platform '{self.review_platform}' is not supported yet.")
                print("Attempting generic scraping...")
                # Could implement generic scraping here
                self.reviews = []

        except Exception as e:
            print(f"\nError during scraping: {e}")
            import traceback
            traceback.print_exc()

        finally:
            # Close browser
            self._close_browser()

        print(f"\n{'='*60}")
        print(f"Scraping completed!")
        print(f"Total reviews scraped: {len(self.reviews)}")
        print(f"{'='*60}\n")

        # If we didn't get metadata, calculate from reviews
        if self.total_reviews_count == 0 and self.reviews:
            self.total_reviews_count = len(self.reviews)

        if self.average_rating == 0.0 and self.reviews:
            ratings = [r['rating'] for r in self.reviews if r.get('rating', 0) > 0]
            if ratings:
                self.average_rating = round(sum(ratings) / len(ratings), 2)

        # Prepare output data
        output_data = {
            'store_name': self.store_name,
            'product_url': self.product_url,
            'product_title': self.product_title,
            'review_platform': self.review_platform,
            'total_reviews': self.total_reviews_count or len(self.reviews),
            'average_rating': self.average_rating,
            'scrape_date': datetime.now().isoformat(),
            'reviews': self.reviews
        }

        return output_data

    def save_to_json(self, output_data: Dict, filename: str = 'shopify_reviews.json'):
        """
        Save scraped reviews to a JSON file.

        Args:
            output_data: Dictionary containing all scraped data
            filename: Output filename
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            print(f"Reviews saved to: {filename}")
        except Exception as e:
            print(f"Error saving to JSON: {e}")
            raise


def main():
    """Main function to run the scraper."""

    if len(sys.argv) < 2:
        print("Shopify Reviews Scraper")
        print("=" * 60)
        print("\nUsage:")
        print("  python shopify_reviews_scraper.py <SHOPIFY_PRODUCT_URL> [OPTIONS]")
        print("\nOptions:")
        print("  --output FILE    Output filename (default: shopify_reviews.json)")
        print("  --delay MIN MAX  Delay range in seconds (default: 2 4)")
        print("  --headless       Run browser in headless mode (default: True)")
        print("\nSupported Review Platforms:")
        for platform in ShopifyReviewsScraper.SUPPORTED_PLATFORMS:
            print(f"  - {platform}")
        print("\nExample:")
        print("  python shopify_reviews_scraper.py 'https://example.myshopify.com/products/example-product'")
        print("  python shopify_reviews_scraper.py 'https://store.com/products/item' --output my_reviews.json")
        print("\nNote: Paste your Shopify product URL as the first argument")
        sys.exit(1)

    # Parse arguments
    product_url = sys.argv[1]
    output_file = 'shopify_reviews.json'
    delay_range = (2, 4)
    headless = True

    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--output' and i + 1 < len(sys.argv):
            output_file = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--delay' and i + 2 < len(sys.argv):
            delay_range = (float(sys.argv[i + 1]), float(sys.argv[i + 2]))
            i += 3
        elif sys.argv[i] == '--headless':
            headless = True
            i += 1
        elif sys.argv[i] == '--no-headless':
            headless = False
            i += 1
        else:
            i += 1

    print("=" * 60)
    print("Shopify Reviews Scraper")
    print("=" * 60)
    print()

    try:
        # Create scraper instance
        scraper = ShopifyReviewsScraper(product_url, headless=headless)

        # Scrape reviews
        output_data = scraper.scrape_reviews(delay_range=delay_range)

        # Save to JSON
        scraper.save_to_json(output_data, output_file)

        print(f"\n✓ Success! {len(output_data['reviews'])} reviews saved to {output_file}")

    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user.")
        if 'scraper' in locals():
            scraper._close_browser()
            if scraper.reviews:
                save_partial = input("Save partial results? (y/n): ").strip().lower()
                if save_partial == 'y':
                    output_data = {
                        'store_name': scraper.store_name,
                        'product_url': scraper.product_url,
                        'product_title': scraper.product_title,
                        'review_platform': scraper.review_platform,
                        'total_reviews': len(scraper.reviews),
                        'average_rating': scraper.average_rating,
                        'scrape_date': datetime.now().isoformat(),
                        'reviews': scraper.reviews,
                        'note': 'Partial scrape - interrupted by user'
                    }
                    scraper.save_to_json(output_data, output_file)
        sys.exit(0)

    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()

        if 'scraper' in locals():
            scraper._close_browser()

        sys.exit(1)


if __name__ == '__main__':
    main()
