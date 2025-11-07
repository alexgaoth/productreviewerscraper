"""
Facebook Product Comments Scraper

Scrapes comments from Facebook posts about products.

WARNING: Facebook has extremely strict anti-scraping measures and terms of service.
This scraper is for educational purposes and authorized testing only.

Recommended Approaches:
1. Official Facebook Graph API (requires app approval)
   https://developers.facebook.com/docs/graph-api/
2. Selenium/Playwright with authenticated sessions
3. facebook-scraper library (unofficial, may break)

Usage:
    python facebook_scraper.py --post-url "https://www.facebook.com/permalink.php?story_fbid=..."
    python facebook_scraper.py --query "iPhone 15 Pro review" --use-selenium
"""

import argparse
import os
from typing import List, Dict, Any, Optional
import re
import time

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("Warning: selenium not installed. Install with: pip install selenium")

from .utils import (
    delay, save_to_json, create_output_structure,
    AuthenticationError, ScraperError, normalize_timestamp
)


class FacebookScraper:
    """
    Scraper for Facebook post comments.

    Note: This implementation uses Selenium for browser automation.
    Requires:
    - ChromeDriver or GeckoDriver
    - Facebook login credentials (for accessing posts)
    - Proper handling of Facebook's dynamic content loading
    """

    BASE_URL = "https://www.facebook.com"

    def __init__(self, email: Optional[str] = None, password: Optional[str] = None, use_selenium: bool = True):
        """
        Initialize Facebook scraper.

        Args:
            email: Facebook account email
            password: Facebook account password
            use_selenium: Whether to use Selenium (required for most scraping)
        """
        if use_selenium and not SELENIUM_AVAILABLE:
            raise ImportError("Selenium is required. Install with: pip install selenium")

        self.email = email or os.getenv('FACEBOOK_EMAIL')
        self.password = password or os.getenv('FACEBOOK_PASSWORD')
        self.use_selenium = use_selenium
        self.driver = None

    def _init_driver(self, headless: bool = False):
        """Initialize Selenium WebDriver."""
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium is required")

        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
        except Exception as e:
            print(f"Failed to initialize Chrome driver: {e}")
            print("Make sure ChromeDriver is installed and in PATH")
            raise

    def _login(self):
        """Login to Facebook using Selenium."""
        if not self.driver:
            self._init_driver()

        if not self.email or not self.password:
            raise AuthenticationError("Facebook credentials required. Set FACEBOOK_EMAIL and FACEBOOK_PASSWORD")

        print("Logging in to Facebook...")

        try:
            self.driver.get(f"{self.BASE_URL}/login")
            time.sleep(2)

            # Find and fill email
            email_input = self.driver.find_element(By.ID, "email")
            email_input.send_keys(self.email)

            # Find and fill password
            password_input = self.driver.find_element(By.ID, "pass")
            password_input.send_keys(self.password)

            # Click login button
            login_button = self.driver.find_element(By.NAME, "login")
            login_button.click()

            # Wait for login to complete
            time.sleep(5)

            # Check if login successful
            if "login" in self.driver.current_url.lower():
                raise AuthenticationError("Login failed. Check credentials or handle 2FA manually.")

            print("Login successful!")

        except Exception as e:
            raise AuthenticationError(f"Failed to login: {e}")

    def _extract_post_id(self, post_url: str) -> str:
        """Extract post ID from Facebook URL."""
        patterns = [
            r'/posts/(\d+)',
            r'story_fbid=(\d+)',
            r'/permalink/(\d+)',
            r'/photos/[^/]+/(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, post_url)
            if match:
                return match.group(1)

        raise ValueError(f"Could not extract post ID from URL: {post_url}")

    def _scroll_to_load_comments(self, max_scrolls: int = 10):
        """Scroll page to load more comments."""
        if not self.driver:
            return

        for i in range(max_scrolls):
            # Scroll to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            # Try to click "View more comments" buttons
            try:
                view_more_buttons = self.driver.find_elements(
                    By.XPATH,
                    "//span[contains(text(), 'View more comments')] | //span[contains(text(), 'more comments')]"
                )
                for button in view_more_buttons:
                    try:
                        button.click()
                        time.sleep(1)
                    except:
                        pass
            except:
                pass

    def _parse_comment_element(self, element, post_id: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single comment element from the page.

        Args:
            element: Selenium WebElement containing comment
            post_id: ID of the parent post

        Returns:
            Dictionary containing comment data
        """
        try:
            comment_data = {}

            # Extract comment text
            # Facebook's DOM structure varies, these are common selectors
            try:
                text_element = element.find_element(By.XPATH, ".//div[contains(@class, 'comment-text')] | .//div[@dir='auto']")
                comment_data['text'] = text_element.text
            except:
                comment_data['text'] = ""

            # Extract author name
            try:
                author_element = element.find_element(By.XPATH, ".//a[contains(@class, 'author')] | .//strong/span | .//a[@role='link']")
                comment_data['author'] = author_element.text
                comment_data['profile_link'] = author_element.get_attribute('href')
            except:
                comment_data['author'] = "Unknown"
                comment_data['profile_link'] = None

            # Extract timestamp
            try:
                time_element = element.find_element(By.XPATH, ".//abbr | .//span[contains(@class, 'timestamp')]")
                timestamp_text = time_element.get_attribute('data-utime') or time_element.text
                comment_data['timestamp'] = normalize_timestamp(timestamp_text)
            except:
                comment_data['timestamp'] = None

            # Extract reactions (likes)
            try:
                like_element = element.find_element(By.XPATH, ".//span[contains(text(), 'Like')] | .//span[contains(@class, 'reaction')]")
                like_text = like_element.text
                like_match = re.search(r'(\d+)', like_text)
                comment_data['likes'] = int(like_match.group(1)) if like_match else 0
            except:
                comment_data['likes'] = 0

            # Extract reply count
            try:
                reply_element = element.find_element(By.XPATH, ".//span[contains(text(), 'reply')] | //span[contains(text(), 'replies')]")
                reply_text = reply_element.text
                reply_match = re.search(r'(\d+)', reply_text)
                comment_data['replies'] = int(reply_match.group(1)) if reply_match else 0
            except:
                comment_data['replies'] = 0

            # Generate comment ID (Facebook doesn't always expose this easily)
            comment_data['id'] = element.get_attribute('id') or f"fb_comment_{hash(comment_data.get('text', ''))}"

            comment_data['rating'] = None
            comment_data['verified_status'] = False

            comment_data['metadata'] = {
                'post_id': post_id,
                'platform_specific_id': element.get_attribute('data-commentid'),
            }

            return comment_data

        except Exception as e:
            print(f"Error parsing comment: {e}")
            return None

    def scrape_post_comments(self, post_url: str, max_scrolls: int = 10) -> List[Dict[str, Any]]:
        """
        Scrape comments from a Facebook post.

        Args:
            post_url: Facebook post URL
            max_scrolls: Maximum number of scrolls to load comments

        Returns:
            List of comment dictionaries
        """
        if not self.driver:
            self._init_driver()
            if self.email and self.password:
                self._login()

        print(f"Scraping Facebook post: {post_url}")

        try:
            post_id = self._extract_post_id(post_url)
        except ValueError:
            post_id = "unknown"

        try:
            self.driver.get(post_url)
            time.sleep(3)

            # Scroll to load comments
            self._scroll_to_load_comments(max_scrolls)

            # Find all comment elements
            # Facebook's structure changes frequently, these are common patterns
            comment_selectors = [
                "//div[@role='article']",
                "//div[contains(@class, 'comment')]",
                "//li[@data-commentid]",
            ]

            comments = []
            for selector in comment_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements:
                        print(f"Found {len(elements)} comment elements with selector: {selector}")
                        for element in elements:
                            comment_data = self._parse_comment_element(element, post_id)
                            if comment_data and comment_data.get('text'):
                                comments.append(comment_data)
                        break
                except Exception as e:
                    continue

            print(f"Successfully parsed {len(comments)} comments")
            return comments

        except Exception as e:
            raise ScraperError(f"Failed to scrape Facebook post: {e}")

    def scrape_by_url(self, post_url: str, max_scrolls: int = 10) -> Dict[str, Any]:
        """
        Scrape comments from a specific Facebook post URL.

        Args:
            post_url: Facebook post URL
            max_scrolls: Maximum scrolls to load comments

        Returns:
            Standardized output dictionary
        """
        comments = self.scrape_post_comments(post_url, max_scrolls=max_scrolls)

        output = create_output_structure(
            platform="facebook",
            product_query=post_url,
            comments=comments,
            additional_data={
                'post_url': post_url,
            }
        )

        return output

    def close(self):
        """Close the Selenium driver."""
        if self.driver:
            self.driver.quit()


def main():
    """Command-line interface for Facebook scraper."""
    parser = argparse.ArgumentParser(
        description="Scrape Facebook post comments",
        epilog="WARNING: Facebook actively blocks scrapers and may ban accounts. "
               "Use official Facebook Graph API for production: https://developers.facebook.com/docs/graph-api/"
    )
    parser.add_argument('--post-url', required=True, help='Facebook post URL')
    parser.add_argument('--email', help='Facebook account email (or set FACEBOOK_EMAIL env var)')
    parser.add_argument('--password', help='Facebook account password (or set FACEBOOK_PASSWORD env var)')
    parser.add_argument('--max-scrolls', type=int, default=10, help='Maximum scrolls to load comments')
    parser.add_argument('--output', default='facebook_comments.json', help='Output JSON file')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')

    args = parser.parse_args()

    print("=" * 80)
    print("WARNING: Facebook scraping violates their Terms of Service")
    print("This tool is for educational purposes and authorized testing only")
    print("Consider using the official Facebook Graph API instead")
    print("https://developers.facebook.com/docs/graph-api/")
    print("=" * 80)
    print()

    scraper = None
    try:
        scraper = FacebookScraper(email=args.email, password=args.password)
        data = scraper.scrape_by_url(args.post_url, max_scrolls=args.max_scrolls)

        save_to_json(data, args.output)
        print(f"\nSuccessfully scraped {data['total_results']} comments!")

    except Exception as e:
        print(f"Error: {e}")
        return 1
    finally:
        if scraper:
            scraper.close()

    return 0


if __name__ == '__main__':
    exit(main())
