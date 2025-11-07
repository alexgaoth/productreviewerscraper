"""
TikTok Product Comments Scraper

Scrapes comments from TikTok videos about products.

WARNING: TikTok has strict anti-scraping measures and frequent API changes.
This scraper is for educational purposes and authorized testing only.

Recommended Approaches:
1. TikTok Research API (requires academic/research approval)
   https://developers.tiktok.com/products/research-api/
2. TikTok-Api Python library (unofficial)
3. Playwright/Selenium with proper session management

Usage:
    python tiktok_scraper.py --video-url "https://www.tiktok.com/@user/video/123456789"
    python tiktok_scraper.py --hashtag "iPhone15Pro" --max-videos 10
"""

import argparse
import os
from typing import List, Dict, Any, Optional
import re
import json
import requests

try:
    from TikTokApi import TikTokApi
    TIKTOK_API_AVAILABLE = True
except ImportError:
    TIKTOK_API_AVAILABLE = False
    print("Warning: TikTokApi not installed. Install with: pip install TikTokApi")

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Warning: playwright not installed. Install with: pip install playwright && playwright install")

from .utils import (
    get_headers, delay, save_to_json, create_output_structure,
    ScraperError, normalize_timestamp
)


class TikTokScraper:
    """
    Scraper for TikTok video comments.

    This implementation supports multiple backends:
    1. TikTokApi library (unofficial, requires MS Playwright)
    2. Direct HTTP requests with proper headers
    3. Playwright browser automation
    """

    BASE_URL = "https://www.tiktok.com"

    def __init__(self, use_api: bool = True):
        """
        Initialize TikTok scraper.

        Args:
            use_api: Whether to use TikTokApi library (requires playwright)
        """
        self.use_api = use_api and TIKTOK_API_AVAILABLE

        if self.use_api:
            if not PLAYWRIGHT_AVAILABLE:
                raise ImportError("Playwright is required for TikTokApi. Install with: pip install playwright && playwright install")

    def _extract_video_id(self, video_url: str) -> str:
        """
        Extract video ID from TikTok URL.

        Args:
            video_url: TikTok video URL

        Returns:
            Video ID
        """
        patterns = [
            r'/video/(\d+)',
            r'/v/(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, video_url)
            if match:
                return match.group(1)

        raise ValueError(f"Could not extract video ID from URL: {video_url}")

    def _parse_comment_api(self, comment_data: Dict[str, Any], video_id: str) -> Dict[str, Any]:
        """
        Parse TikTok comment from TikTokApi response.

        Args:
            comment_data: Raw comment data from API
            video_id: ID of the parent video

        Returns:
            Standardized comment dictionary
        """
        try:
            user = comment_data.get('user', {})

            comment = {
                'id': comment_data.get('cid', ''),
                'text': comment_data.get('text', ''),
                'author': user.get('unique_id', user.get('nickname', 'Unknown')),
                'timestamp': normalize_timestamp(comment_data.get('create_time')),
                'likes': comment_data.get('digg_count', 0),
                'replies': comment_data.get('reply_comment_total', 0),
                'rating': None,
                'profile_link': f"{self.BASE_URL}/@{user.get('unique_id')}" if user.get('unique_id') else None,
                'verified_status': user.get('verified', False) or user.get('custom_verify', '') != '',
                'metadata': {
                    'video_id': video_id,
                    'comment_language': comment_data.get('comment_language', ''),
                    'user_id': user.get('uid', ''),
                    'is_author_digged': comment_data.get('is_author_digged', False),
                    'share_count': comment_data.get('share_count', 0),
                    'reply_id': comment_data.get('reply_id', None),
                    'user_follower_count': user.get('follower_count', 0),
                    'user_avatar': user.get('avatar_thumb', {}).get('url_list', [None])[0],
                }
            }

            return comment

        except Exception as e:
            print(f"Error parsing comment: {e}")
            return None

    def scrape_video_comments_api(self, video_id: str, max_comments: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Scrape comments using TikTokApi library.

        Args:
            video_id: TikTok video ID
            max_comments: Maximum number of comments to retrieve

        Returns:
            List of comment dictionaries
        """
        if not TIKTOK_API_AVAILABLE:
            raise ImportError("TikTokApi is required. Install with: pip install TikTokApi")

        print(f"Scraping comments for video: {video_id}")

        try:
            with TikTokApi() as api:
                comments = []
                comment_count = 0

                # Get comments for the video
                for comment in api.video(id=video_id).comments():
                    parsed_comment = self._parse_comment_api(comment.as_dict, video_id)
                    if parsed_comment:
                        comments.append(parsed_comment)
                        comment_count += 1

                        if max_comments and comment_count >= max_comments:
                            break

                print(f"Found {len(comments)} comments")
                return comments

        except Exception as e:
            raise ScraperError(f"Failed to scrape TikTok video with API: {e}")

    def scrape_video_comments_http(self, video_id: str, max_comments: Optional[int] = 100) -> List[Dict[str, Any]]:
        """
        Scrape comments using direct HTTP requests to TikTok's API endpoints.

        Note: This method may not work without proper authentication/cookies.

        Args:
            video_id: TikTok video ID
            max_comments: Maximum number of comments to retrieve

        Returns:
            List of comment dictionaries
        """
        print(f"Scraping comments for video: {video_id} (HTTP method)")

        comments = []

        try:
            # TikTok's comment API endpoint (may change)
            api_url = "https://www.tiktok.com/api/comment/list/"

            params = {
                'aweme_id': video_id,
                'count': min(max_comments or 100, 100),
                'cursor': 0,
            }

            headers = get_headers({
                'Referer': f'{self.BASE_URL}/@/video/{video_id}',
            })

            response = requests.get(api_url, params=params, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                comment_list = data.get('comments', [])

                for comment_data in comment_list:
                    parsed_comment = self._parse_comment_api(comment_data, video_id)
                    if parsed_comment:
                        comments.append(parsed_comment)

                print(f"Found {len(comments)} comments")
            else:
                print(f"Failed to fetch comments: HTTP {response.status_code}")
                print("Note: TikTok's API may require authentication or have changed endpoints")

        except Exception as e:
            print(f"Error scraping with HTTP method: {e}")
            print("Falling back to alternative methods may be required")

        return comments

    def scrape_by_url(self, video_url: str, max_comments: Optional[int] = None) -> Dict[str, Any]:
        """
        Scrape comments from a specific TikTok video URL.

        Args:
            video_url: TikTok video URL
            max_comments: Maximum comments to retrieve

        Returns:
            Standardized output dictionary
        """
        video_id = self._extract_video_id(video_url)

        # Try API method first, fall back to HTTP
        if self.use_api:
            try:
                comments = self.scrape_video_comments_api(video_id, max_comments=max_comments)
            except Exception as e:
                print(f"API method failed: {e}")
                print("Trying HTTP method...")
                comments = self.scrape_video_comments_http(video_id, max_comments=max_comments)
        else:
            comments = self.scrape_video_comments_http(video_id, max_comments=max_comments)

        output = create_output_structure(
            platform="tiktok",
            product_query=video_url,
            comments=comments,
            additional_data={
                'video_id': video_id,
                'video_url': video_url,
            }
        )

        return output

    def scrape_by_hashtag(
        self,
        hashtag: str,
        max_videos: int = 10,
        max_comments_per_video: Optional[int] = 50
    ) -> Dict[str, Any]:
        """
        Scrape comments from videos with a specific hashtag.

        Args:
            hashtag: Hashtag to search (without #)
            max_videos: Maximum videos to scrape
            max_comments_per_video: Maximum comments per video

        Returns:
            Standardized output dictionary
        """
        if not TIKTOK_API_AVAILABLE:
            raise ImportError("TikTokApi is required for hashtag search. Install with: pip install TikTokApi")

        print(f"Scraping TikTok videos with hashtag: #{hashtag}")

        try:
            with TikTokApi() as api:
                all_comments = []
                videos_scraped = 0

                # Get videos for hashtag
                hashtag_obj = api.hashtag(name=hashtag)

                for video in hashtag_obj.videos(count=max_videos):
                    videos_scraped += 1
                    video_id = video.id

                    print(f"\nScraping video {videos_scraped}/{max_videos}: {video_id}")

                    try:
                        comments = self.scrape_video_comments_api(video_id, max_comments=max_comments_per_video)

                        # Add video context to comments
                        for comment in comments:
                            comment['metadata']['video_url'] = f"{self.BASE_URL}/@/video/{video_id}"
                            comment['metadata']['hashtag'] = hashtag

                        all_comments.extend(comments)

                    except Exception as e:
                        print(f"Error scraping video {video_id}: {e}")

                    # Delay between videos
                    if videos_scraped < max_videos:
                        delay(2, 4)

                print(f"\nTotal comments collected: {len(all_comments)}")

                output = create_output_structure(
                    platform="tiktok",
                    product_query=f"#{hashtag}",
                    comments=all_comments,
                    additional_data={
                        'hashtag': hashtag,
                        'videos_scraped': videos_scraped,
                    }
                )

                return output

        except Exception as e:
            raise ScraperError(f"Failed to scrape hashtag: {e}")

    def scrape_by_user(
        self,
        username: str,
        max_videos: int = 10,
        max_comments_per_video: Optional[int] = 50
    ) -> Dict[str, Any]:
        """
        Scrape comments from a user's videos (useful for brand accounts).

        Args:
            username: TikTok username (with or without @)
            max_videos: Maximum videos to scrape
            max_comments_per_video: Maximum comments per video

        Returns:
            Standardized output dictionary
        """
        if not TIKTOK_API_AVAILABLE:
            raise ImportError("TikTokApi is required for user scraping. Install with: pip install TikTokApi")

        # Remove @ if present
        username = username.lstrip('@')

        print(f"Scraping videos from user: @{username}")

        try:
            with TikTokApi() as api:
                all_comments = []
                videos_scraped = 0

                # Get user's videos
                user = api.user(username=username)

                for video in user.videos(count=max_videos):
                    videos_scraped += 1
                    video_id = video.id

                    print(f"\nScraping video {videos_scraped}/{max_videos}: {video_id}")

                    try:
                        comments = self.scrape_video_comments_api(video_id, max_comments=max_comments_per_video)

                        # Add video context to comments
                        for comment in comments:
                            comment['metadata']['video_url'] = f"{self.BASE_URL}/@{username}/video/{video_id}"
                            comment['metadata']['creator_username'] = username

                        all_comments.extend(comments)

                    except Exception as e:
                        print(f"Error scraping video {video_id}: {e}")

                    # Delay between videos
                    if videos_scraped < max_videos:
                        delay(2, 4)

                print(f"\nTotal comments collected: {len(all_comments)}")

                output = create_output_structure(
                    platform="tiktok",
                    product_query=f"@{username}",
                    comments=all_comments,
                    additional_data={
                        'username': username,
                        'videos_scraped': videos_scraped,
                    }
                )

                return output

        except Exception as e:
            raise ScraperError(f"Failed to scrape user: {e}")


def main():
    """Command-line interface for TikTok scraper."""
    parser = argparse.ArgumentParser(
        description="Scrape TikTok video comments",
        epilog="WARNING: TikTok actively blocks scrapers. "
               "Consider using TikTok Research API for authorized access: https://developers.tiktok.com/products/research-api/"
    )
    parser.add_argument('--video-url', help='TikTok video URL')
    parser.add_argument('--hashtag', help='Hashtag to search (without #)')
    parser.add_argument('--user', help='Username to scrape videos from')
    parser.add_argument('--max-videos', type=int, default=10, help='Maximum videos to scrape (for hashtag/user)')
    parser.add_argument('--max-comments', type=int, help='Maximum comments per video')
    parser.add_argument('--use-api', action='store_true', default=True, help='Use TikTokApi library (default)')
    parser.add_argument('--use-http', action='store_true', help='Use HTTP requests instead of API library')
    parser.add_argument('--output', default='tiktok_comments.json', help='Output JSON file')

    args = parser.parse_args()

    if not any([args.video_url, args.hashtag, args.user]):
        parser.error("Either --video-url, --hashtag, or --user must be specified")

    print("=" * 80)
    print("WARNING: TikTok scraping may violate their Terms of Service")
    print("This tool is for educational purposes and authorized testing only")
    print("Consider using the TikTok Research API for legitimate access")
    print("https://developers.tiktok.com/products/research-api/")
    print("=" * 80)
    print()

    try:
        use_api = args.use_api and not args.use_http
        scraper = TikTokScraper(use_api=use_api)

        if args.video_url:
            data = scraper.scrape_by_url(args.video_url, max_comments=args.max_comments)
        elif args.hashtag:
            data = scraper.scrape_by_hashtag(args.hashtag, max_videos=args.max_videos, max_comments_per_video=args.max_comments)
        elif args.user:
            data = scraper.scrape_by_user(args.user, max_videos=args.max_videos, max_comments_per_video=args.max_comments)

        save_to_json(data, args.output)
        print(f"\nSuccessfully scraped {data['total_results']} comments!")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
