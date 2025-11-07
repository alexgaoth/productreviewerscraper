"""
Instagram Product Comments Scraper

Scrapes comments from Instagram posts about products.

WARNING: Instagram has extremely strict anti-scraping measures.
This scraper is for educational purposes and authorized testing only.

Recommended Approaches:
1. Official Instagram Graph API (requires Facebook Business account)
   https://developers.facebook.com/docs/instagram-api/
2. instaloader library (unofficial, may require login)
3. Selenium/Playwright with authenticated sessions

Usage:
    python instagram_scraper.py --post-url "https://www.instagram.com/p/ABC123/"
    python instagram_scraper.py --hashtag "iPhone15Pro" --max-posts 10
"""

import argparse
import os
from typing import List, Dict, Any, Optional
import re
import json

try:
    import instaloader
    INSTALOADER_AVAILABLE = True
except ImportError:
    INSTALOADER_AVAILABLE = False
    print("Warning: instaloader not installed. Install with: pip install instaloader")

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    import time
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

from .utils import (
    delay, save_to_json, create_output_structure,
    AuthenticationError, ScraperError, normalize_timestamp
)


class InstagramScraper:
    """
    Scraper for Instagram post comments.

    Uses instaloader library for accessing Instagram data.
    Requires Instagram login for most operations.
    """

    BASE_URL = "https://www.instagram.com"

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None, use_instaloader: bool = True):
        """
        Initialize Instagram scraper.

        Args:
            username: Instagram username
            password: Instagram password
            use_instaloader: Whether to use instaloader library (recommended)
        """
        self.username = username or os.getenv('INSTAGRAM_USERNAME')
        self.password = password or os.getenv('INSTAGRAM_PASSWORD')
        self.use_instaloader = use_instaloader

        if use_instaloader and not INSTALOADER_AVAILABLE:
            raise ImportError("instaloader is required. Install with: pip install instaloader")

        if use_instaloader:
            self.loader = instaloader.Instaloader()

            # Login if credentials provided
            if self.username and self.password:
                self._login_instaloader()

    def _login_instaloader(self):
        """Login to Instagram using instaloader."""
        print(f"Logging in to Instagram as {self.username}...")
        try:
            self.loader.login(self.username, self.password)
            print("Login successful!")
        except Exception as e:
            raise AuthenticationError(f"Failed to login to Instagram: {e}")

    def _extract_shortcode(self, post_url: str) -> str:
        """
        Extract shortcode from Instagram post URL.

        Args:
            post_url: Instagram post URL

        Returns:
            Post shortcode
        """
        patterns = [
            r'/p/([A-Za-z0-9_-]+)',
            r'/reel/([A-Za-z0-9_-]+)',
            r'/tv/([A-Za-z0-9_-]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, post_url)
            if match:
                return match.group(1)

        raise ValueError(f"Could not extract shortcode from URL: {post_url}")

    def _parse_comment(self, comment, post_shortcode: str) -> Dict[str, Any]:
        """
        Parse an Instagram comment from instaloader.

        Args:
            comment: Instaloader comment object
            post_shortcode: Shortcode of the parent post

        Returns:
            Standardized comment dictionary
        """
        try:
            comment_data = {
                'id': str(comment.id),
                'text': comment.text,
                'author': comment.owner.username,
                'timestamp': normalize_timestamp(comment.created_at_utc),
                'likes': comment.likes_count if hasattr(comment, 'likes_count') else 0,
                'replies': comment.answers if hasattr(comment, 'answers') else 0,
                'rating': None,
                'profile_link': f"{self.BASE_URL}/{comment.owner.username}/",
                'verified_status': comment.owner.is_verified if hasattr(comment.owner, 'is_verified') else False,
                'metadata': {
                    'post_shortcode': post_shortcode,
                    'comment_id': comment.id,
                    'owner_id': comment.owner.userid if hasattr(comment.owner, 'userid') else None,
                    'is_reply': False,  # Top-level comment
                }
            }

            return comment_data

        except Exception as e:
            print(f"Error parsing comment: {e}")
            return None

    def scrape_post_comments(self, shortcode: str, max_comments: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Scrape comments from an Instagram post.

        Args:
            shortcode: Instagram post shortcode
            max_comments: Maximum number of comments to retrieve

        Returns:
            List of comment dictionaries
        """
        if not INSTALOADER_AVAILABLE:
            raise ImportError("instaloader is required")

        print(f"Scraping comments for post: {shortcode}")

        try:
            post = instaloader.Post.from_shortcode(self.loader.context, shortcode)

            comments = []
            comment_count = 0

            for comment in post.get_comments():
                parsed_comment = self._parse_comment(comment, shortcode)
                if parsed_comment:
                    comments.append(parsed_comment)
                    comment_count += 1

                    if max_comments and comment_count >= max_comments:
                        break

                # Small delay to avoid rate limiting
                if comment_count % 50 == 0:
                    delay(1, 2)

            print(f"Found {len(comments)} comments")
            return comments

        except Exception as e:
            raise ScraperError(f"Failed to scrape Instagram post: {e}")

    def scrape_by_url(self, post_url: str, max_comments: Optional[int] = None) -> Dict[str, Any]:
        """
        Scrape comments from a specific Instagram post URL.

        Args:
            post_url: Instagram post URL
            max_comments: Maximum comments to retrieve

        Returns:
            Standardized output dictionary
        """
        shortcode = self._extract_shortcode(post_url)
        comments = self.scrape_post_comments(shortcode, max_comments=max_comments)

        # Get post metadata
        try:
            post = instaloader.Post.from_shortcode(self.loader.context, shortcode)
            additional_data = {
                'post_url': post_url,
                'post_shortcode': shortcode,
                'post_owner': post.owner_username,
                'post_likes': post.likes,
                'post_caption': post.caption if hasattr(post, 'caption') else None,
                'post_timestamp': normalize_timestamp(post.date_utc),
            }
        except:
            additional_data = {
                'post_url': post_url,
                'post_shortcode': shortcode,
            }

        output = create_output_structure(
            platform="instagram",
            product_query=post_url,
            comments=comments,
            additional_data=additional_data
        )

        return output

    def scrape_by_hashtag(
        self,
        hashtag: str,
        max_posts: int = 10,
        max_comments_per_post: Optional[int] = 50
    ) -> Dict[str, Any]:
        """
        Scrape comments from posts with a specific hashtag.

        Args:
            hashtag: Hashtag to search (without #)
            max_posts: Maximum posts to scrape
            max_comments_per_post: Maximum comments per post

        Returns:
            Standardized output dictionary
        """
        if not INSTALOADER_AVAILABLE:
            raise ImportError("instaloader is required")

        print(f"Scraping Instagram posts with hashtag: #{hashtag}")

        try:
            hashtag_obj = instaloader.Hashtag.from_name(self.loader.context, hashtag)

            all_comments = []
            posts_scraped = 0

            for post in hashtag_obj.get_posts():
                if posts_scraped >= max_posts:
                    break

                posts_scraped += 1
                print(f"\nScraping post {posts_scraped}/{max_posts}: {post.shortcode}")

                try:
                    comments = self.scrape_post_comments(post.shortcode, max_comments=max_comments_per_post)

                    # Add post context to comments
                    for comment in comments:
                        comment['metadata']['post_url'] = f"{self.BASE_URL}/p/{post.shortcode}/"
                        comment['metadata']['hashtag'] = hashtag

                    all_comments.extend(comments)

                except Exception as e:
                    print(f"Error scraping post {post.shortcode}: {e}")

                # Delay between posts
                if posts_scraped < max_posts:
                    delay(3, 5)

            print(f"\nTotal comments collected: {len(all_comments)}")

            output = create_output_structure(
                platform="instagram",
                product_query=f"#{hashtag}",
                comments=all_comments,
                additional_data={
                    'hashtag': hashtag,
                    'posts_scraped': posts_scraped,
                }
            )

            return output

        except Exception as e:
            raise ScraperError(f"Failed to scrape hashtag: {e}")

    def scrape_by_user(
        self,
        username: str,
        max_posts: int = 10,
        max_comments_per_post: Optional[int] = 50
    ) -> Dict[str, Any]:
        """
        Scrape comments from a user's posts (useful for brand accounts).

        Args:
            username: Instagram username
            max_posts: Maximum posts to scrape
            max_comments_per_post: Maximum comments per post

        Returns:
            Standardized output dictionary
        """
        if not INSTALOADER_AVAILABLE:
            raise ImportError("instaloader is required")

        print(f"Scraping posts from user: @{username}")

        try:
            profile = instaloader.Profile.from_username(self.loader.context, username)

            all_comments = []
            posts_scraped = 0

            for post in profile.get_posts():
                if posts_scraped >= max_posts:
                    break

                posts_scraped += 1
                print(f"\nScraping post {posts_scraped}/{max_posts}: {post.shortcode}")

                try:
                    comments = self.scrape_post_comments(post.shortcode, max_comments=max_comments_per_post)

                    # Add post context to comments
                    for comment in comments:
                        comment['metadata']['post_url'] = f"{self.BASE_URL}/p/{post.shortcode}/"
                        comment['metadata']['profile_username'] = username

                    all_comments.extend(comments)

                except Exception as e:
                    print(f"Error scraping post {post.shortcode}: {e}")

                # Delay between posts
                if posts_scraped < max_posts:
                    delay(3, 5)

            print(f"\nTotal comments collected: {len(all_comments)}")

            output = create_output_structure(
                platform="instagram",
                product_query=f"@{username}",
                comments=all_comments,
                additional_data={
                    'profile_username': username,
                    'posts_scraped': posts_scraped,
                }
            )

            return output

        except Exception as e:
            raise ScraperError(f"Failed to scrape user profile: {e}")


def main():
    """Command-line interface for Instagram scraper."""
    parser = argparse.ArgumentParser(
        description="Scrape Instagram post comments",
        epilog="WARNING: Instagram actively blocks scrapers and may ban accounts. "
               "Use official Instagram Graph API for production: https://developers.facebook.com/docs/instagram-api/"
    )
    parser.add_argument('--post-url', help='Instagram post URL')
    parser.add_argument('--hashtag', help='Hashtag to search (without #)')
    parser.add_argument('--user', help='Username to scrape posts from')
    parser.add_argument('--username', help='Instagram login username (or set INSTAGRAM_USERNAME env var)')
    parser.add_argument('--password', help='Instagram login password (or set INSTAGRAM_PASSWORD env var)')
    parser.add_argument('--max-posts', type=int, default=10, help='Maximum posts to scrape (for hashtag/user)')
    parser.add_argument('--max-comments', type=int, help='Maximum comments per post')
    parser.add_argument('--output', default='instagram_comments.json', help='Output JSON file')

    args = parser.parse_args()

    if not any([args.post_url, args.hashtag, args.user]):
        parser.error("Either --post-url, --hashtag, or --user must be specified")

    print("=" * 80)
    print("WARNING: Instagram scraping may violate their Terms of Service")
    print("This tool is for educational purposes and authorized testing only")
    print("Consider using the official Instagram Graph API instead")
    print("https://developers.facebook.com/docs/instagram-api/")
    print("=" * 80)
    print()

    try:
        scraper = InstagramScraper(username=args.username, password=args.password)

        if args.post_url:
            data = scraper.scrape_by_url(args.post_url, max_comments=args.max_comments)
        elif args.hashtag:
            data = scraper.scrape_by_hashtag(args.hashtag, max_posts=args.max_posts, max_comments_per_post=args.max_comments)
        elif args.user:
            data = scraper.scrape_by_user(args.user, max_posts=args.max_posts, max_comments_per_post=args.max_comments)

        save_to_json(data, args.output)
        print(f"\nSuccessfully scraped {data['total_results']} comments!")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
