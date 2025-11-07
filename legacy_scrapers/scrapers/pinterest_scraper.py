"""
Pinterest Product Comments Scraper

Scrapes comments from Pinterest pins related to products.

Note: Pinterest has strict anti-scraping measures. This scraper uses:
1. Pinterest's unofficial API endpoints
2. Proper authentication and session management
3. Rate limiting to avoid detection

Alternative: Consider using Pinterest API (requires business account)
https://developers.pinterest.com/

Usage:
    python pinterest_scraper.py --query "iPhone 15 Pro review"
    python pinterest_scraper.py --pin-url "https://www.pinterest.com/pin/123456789/"
"""

import argparse
import requests
from typing import List, Dict, Any, Optional
import json
import re
from urllib.parse import urlencode, quote

from .utils import (
    get_headers, delay, save_to_json, create_output_structure,
    RateLimitError, ScraperError, normalize_timestamp
)


class PinterestScraper:
    """
    Scraper for Pinterest pin comments.

    Note: Pinterest heavily protects its data. This scraper attempts to use
    their internal API endpoints, but may require:
    - Valid session cookies
    - Additional authentication headers
    - Proxies for high-volume scraping
    """

    BASE_URL = "https://www.pinterest.com"
    API_BASE = "https://www.pinterest.com/resource"

    def __init__(self, session_cookie: Optional[str] = None):
        """
        Initialize Pinterest scraper.

        Args:
            session_cookie: Optional Pinterest session cookie (_pinterest_sess)
                           for authenticated requests
        """
        self.session = requests.Session()
        self.session_cookie = session_cookie

        # Set up session with cookies if provided
        if session_cookie:
            self.session.cookies.set('_pinterest_sess', session_cookie, domain='.pinterest.com')

    def _get_api_headers(self) -> Dict[str, str]:
        """Get headers for Pinterest API requests."""
        headers = get_headers({
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'X-Pinterest-AppState': 'active',
            'Referer': 'https://www.pinterest.com/',
            'Origin': 'https://www.pinterest.com',
        })
        return headers

    def _extract_pin_id(self, pin_url: str) -> str:
        """
        Extract pin ID from Pinterest URL.

        Args:
            pin_url: Pinterest pin URL

        Returns:
            Pin ID string
        """
        patterns = [
            r'/pin/(\d+)/',
            r'/pin/(\d+)$',
        ]

        for pattern in patterns:
            match = re.search(pattern, pin_url)
            if match:
                return match.group(1)

        raise ValueError(f"Could not extract pin ID from URL: {pin_url}")

    def _parse_comment(self, comment_data: Dict[str, Any], pin_id: str) -> Dict[str, Any]:
        """
        Parse a Pinterest comment from API response.

        Args:
            comment_data: Raw comment data from API
            pin_id: ID of the pin

        Returns:
            Standardized comment dictionary
        """
        try:
            # Pinterest API structure (may vary)
            commenter = comment_data.get('commenter', {})

            comment = {
                'id': comment_data.get('id', ''),
                'text': comment_data.get('text', ''),
                'author': commenter.get('username', commenter.get('full_name', 'Anonymous')),
                'timestamp': normalize_timestamp(comment_data.get('created_at')),
                'likes': comment_data.get('like_count', 0),
                'replies': comment_data.get('reply_count', 0),
                'rating': None,
                'profile_link': f"https://www.pinterest.com/{commenter.get('username')}/" if commenter.get('username') else None,
                'verified_status': commenter.get('verified', False),
                'metadata': {
                    'pin_id': pin_id,
                    'commenter_id': commenter.get('id'),
                    'commenter_image': commenter.get('image_small_url'),
                    'commenter_follower_count': commenter.get('follower_count', 0),
                }
            }

            return comment

        except Exception as e:
            print(f"Error parsing comment: {e}")
            return None

    def scrape_pin_comments(self, pin_id: str, max_comments: int = 100) -> List[Dict[str, Any]]:
        """
        Scrape comments from a Pinterest pin.

        Args:
            pin_id: Pinterest pin ID
            max_comments: Maximum number of comments to retrieve

        Returns:
            List of comment dictionaries
        """
        print(f"Scraping comments for pin: {pin_id}")

        comments = []

        try:
            # Pinterest uses a GraphQL-like API structure
            # This is a simplified version - actual implementation may need adjustments

            # Attempt 1: Try to access pin page and extract data from initial state
            pin_url = f"{self.BASE_URL}/pin/{pin_id}/"
            response = self.session.get(pin_url, headers=self._get_api_headers(), timeout=30)
            response.raise_for_status()

            # Look for initial data in the page
            # Pinterest embeds data in <script> tags with JSON
            initial_data_match = re.search(r'<script[^>]*id="initial-state"[^>]*>(.*?)</script>',
                                          response.text, re.DOTALL)

            if initial_data_match:
                try:
                    initial_data = json.loads(initial_data_match.group(1))
                    # Navigate through the nested structure to find comments
                    # Structure varies, but typically: resources -> PinResource -> data -> comments

                    # This is a placeholder - actual structure needs to be discovered
                    print("Found initial data - parsing comments...")
                    # Comment extraction would go here

                except json.JSONDecodeError:
                    print("Could not parse initial data JSON")

            # Attempt 2: Use Pinterest's internal API endpoint
            # Note: This endpoint structure may change
            api_url = f"{self.API_BASE}/AggregatedCommentsFeedResource/get/"

            params = {
                'source_url': f'/pin/{pin_id}/',
                'data': json.dumps({
                    'options': {
                        'pin_id': pin_id,
                        'page_size': min(max_comments, 50),
                    }
                })
            }

            api_response = self.session.get(
                api_url,
                params=params,
                headers=self._get_api_headers(),
                timeout=30
            )

            if api_response.status_code == 200:
                data = api_response.json()

                # Parse response structure (varies by API version)
                resource_data = data.get('resource_response', {}).get('data', [])

                for item in resource_data:
                    parsed_comment = self._parse_comment(item, pin_id)
                    if parsed_comment:
                        comments.append(parsed_comment)

            delay(1, 2)

        except requests.exceptions.RequestException as e:
            print(f"Error fetching pin data: {e}")
            raise ScraperError(f"Failed to fetch Pinterest pin: {e}")

        return comments

    def search_pins(self, query: str, limit: int = 20) -> List[str]:
        """
        Search for pins related to a product query.

        Args:
            query: Search query (product name)
            limit: Maximum number of pins to find

        Returns:
            List of pin IDs
        """
        print(f"Searching Pinterest for: '{query}'")

        pin_ids = []

        try:
            # Pinterest search API endpoint (may require authentication)
            search_url = f"{self.BASE_URL}/resource/BaseSearchResource/get/"

            params = {
                'source_url': f'/search/pins/?q={quote(query)}',
                'data': json.dumps({
                    'options': {
                        'query': query,
                        'scope': 'pins',
                        'page_size': min(limit, 25),
                    }
                })
            }

            response = self.session.get(
                search_url,
                params=params,
                headers=self._get_api_headers(),
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                results = data.get('resource_response', {}).get('data', {}).get('results', [])

                for result in results[:limit]:
                    pin_id = result.get('id')
                    if pin_id:
                        pin_ids.append(pin_id)

                print(f"Found {len(pin_ids)} pins")
            else:
                print(f"Search failed with status {response.status_code}")

        except Exception as e:
            print(f"Error searching Pinterest: {e}")

        return pin_ids

    def scrape_by_url(self, pin_url: str) -> Dict[str, Any]:
        """
        Scrape comments from a specific Pinterest pin URL.

        Args:
            pin_url: Pinterest pin URL

        Returns:
            Standardized output dictionary
        """
        pin_id = self._extract_pin_id(pin_url)
        comments = self.scrape_pin_comments(pin_id)

        output = create_output_structure(
            platform="pinterest",
            product_query=pin_url,
            comments=comments,
            additional_data={
                'pin_id': pin_id,
                'pin_url': pin_url,
            }
        )

        return output

    def scrape_by_search(self, query: str, max_pins: int = 10, max_comments_per_pin: int = 50) -> Dict[str, Any]:
        """
        Search for pins and scrape their comments.

        Args:
            query: Search query
            max_pins: Maximum pins to scrape
            max_comments_per_pin: Maximum comments per pin

        Returns:
            Standardized output dictionary
        """
        pin_ids = self.search_pins(query, limit=max_pins)

        all_comments = []

        for i, pin_id in enumerate(pin_ids, 1):
            print(f"\nScraping pin {i}/{len(pin_ids)}: {pin_id}")
            comments = self.scrape_pin_comments(pin_id, max_comments=max_comments_per_pin)

            # Add pin context to comments
            for comment in comments:
                comment['metadata']['pin_url'] = f"{self.BASE_URL}/pin/{pin_id}/"

            all_comments.extend(comments)

            if i < len(pin_ids):
                delay(2, 4)

        output = create_output_structure(
            platform="pinterest",
            product_query=query,
            comments=all_comments,
            additional_data={
                'pins_scraped': len(pin_ids),
            }
        )

        return output


def main():
    """Command-line interface for Pinterest scraper."""
    parser = argparse.ArgumentParser(
        description="Scrape Pinterest pin comments",
        epilog="Note: Pinterest has strict anti-scraping measures. "
               "Consider using official Pinterest API for production use."
    )
    parser.add_argument('--query', help='Search query for pins')
    parser.add_argument('--pin-url', help='Specific pin URL to scrape')
    parser.add_argument('--max-pins', type=int, default=10, help='Maximum pins to scrape (for search)')
    parser.add_argument('--max-comments', type=int, default=50, help='Maximum comments per pin')
    parser.add_argument('--session-cookie', help='Pinterest session cookie (_pinterest_sess) for authenticated access')
    parser.add_argument('--output', default='pinterest_comments.json', help='Output JSON file')

    args = parser.parse_args()

    if not args.query and not args.pin_url:
        parser.error("Either --query or --pin-url must be specified")

    print("WARNING: Pinterest actively blocks scrapers. This tool may not work without:")
    print("  1. Valid session cookies from a logged-in account")
    print("  2. Proxies to rotate IP addresses")
    print("  3. Extended delays between requests")
    print("\nConsider using the official Pinterest API: https://developers.pinterest.com/\n")

    try:
        scraper = PinterestScraper(session_cookie=args.session_cookie)

        if args.pin_url:
            data = scraper.scrape_by_url(args.pin_url)
        else:
            data = scraper.scrape_by_search(
                args.query,
                max_pins=args.max_pins,
                max_comments_per_pin=args.max_comments
            )

        save_to_json(data, args.output)
        print(f"\nSuccessfully scraped {data['total_results']} comments!")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
