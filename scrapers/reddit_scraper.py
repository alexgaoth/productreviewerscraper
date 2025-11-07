"""
Reddit Product Discussion Scraper

Scrapes product-related posts and comments from Reddit.
Can search by product name or scrape specific posts/subreddits.

Usage:
    python reddit_scraper.py --query "iPhone 15 Pro review"
    python reddit_scraper.py --query "iPhone 15 Pro" --subreddit "apple" --limit 100
    python reddit_scraper.py --url "https://www.reddit.com/r/apple/comments/..."

Requirements:
    - PRAW (Python Reddit API Wrapper)
    - Reddit API credentials (create app at https://www.reddit.com/prefs/apps)

Configuration:
    Set environment variables or create .env file:
    - REDDIT_CLIENT_ID
    - REDDIT_CLIENT_SECRET
    - REDDIT_USER_AGENT (e.g., "ProductReviewScraper/1.0")
"""

import argparse
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import re

try:
    import praw
    from praw.models import MoreComments
except ImportError:
    praw = None
    print("Warning: praw not installed. Install with: pip install praw")

from .utils import (
    save_to_json, create_output_structure,
    AuthenticationError, ScraperError, normalize_timestamp
)


class RedditScraper:
    """Scraper for Reddit posts and comments about products."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """
        Initialize Reddit scraper with API credentials.

        Args:
            client_id: Reddit API client ID
            client_secret: Reddit API client secret
            user_agent: User agent string for API requests

        Raises:
            AuthenticationError: If credentials are missing or invalid
        """
        if praw is None:
            raise ImportError("praw library is required. Install with: pip install praw")

        self.client_id = client_id or os.getenv('REDDIT_CLIENT_ID')
        self.client_secret = client_secret or os.getenv('REDDIT_CLIENT_SECRET')
        self.user_agent = user_agent or os.getenv('REDDIT_USER_AGENT', 'ProductReviewScraper/1.0')

        if not all([self.client_id, self.client_secret]):
            raise AuthenticationError(
                "Reddit API credentials required. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET environment variables."
            )

        try:
            self.reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent
            )
            # Test authentication
            self.reddit.user.me()
        except Exception as e:
            raise AuthenticationError(f"Failed to authenticate with Reddit API: {e}")

    def _parse_comment(self, comment, post_id: str) -> Dict[str, Any]:
        """
        Parse a Reddit comment into standardized format.

        Args:
            comment: PRAW comment object
            post_id: ID of the parent post

        Returns:
            Dictionary containing comment data
        """
        comment_data = {
            'id': comment.id,
            'text': comment.body,
            'author': str(comment.author) if comment.author else '[deleted]',
            'timestamp': normalize_timestamp(comment.created_utc),
            'likes': comment.score,
            'replies': len(comment.replies) if hasattr(comment, 'replies') else 0,
            'rating': None,  # Reddit doesn't have star ratings
            'profile_link': f"https://www.reddit.com/user/{comment.author}" if comment.author else None,
            'verified_status': False,  # Reddit doesn't have verified status for regular users
            'metadata': {
                'post_id': post_id,
                'comment_url': f"https://www.reddit.com{comment.permalink}",
                'is_submitter': comment.is_submitter,
                'edited': comment.edited if comment.edited else False,
                'distinguished': comment.distinguished,  # mod/admin status
                'stickied': comment.stickied,
                'gilded': comment.gilded,
                'awards': self._extract_awards(comment),
                'controversiality': comment.controversiality,
            }
        }

        return comment_data

    def _extract_awards(self, comment) -> List[Dict[str, Any]]:
        """Extract award information from a comment."""
        awards = []
        if hasattr(comment, 'all_awardings'):
            for award in comment.all_awardings:
                awards.append({
                    'name': award.get('name', ''),
                    'count': award.get('count', 0),
                    'icon_url': award.get('icon_url', ''),
                })
        return awards

    def _extract_all_comments(self, submission, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Recursively extract all comments from a submission.

        Args:
            submission: PRAW submission object
            limit: Maximum number of comments to extract

        Returns:
            List of comment dictionaries
        """
        comments = []

        # Replace MoreComments objects to load all comments
        submission.comments.replace_more(limit=0)

        comment_count = 0
        for comment in submission.comments.list():
            if isinstance(comment, MoreComments):
                continue

            comment_data = self._parse_comment(comment, submission.id)
            comments.append(comment_data)

            comment_count += 1
            if limit and comment_count >= limit:
                break

        return comments

    def scrape_by_url(self, url: str, comment_limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Scrape comments from a specific Reddit post URL.

        Args:
            url: Reddit post URL
            comment_limit: Maximum number of comments to extract

        Returns:
            Standardized output dictionary
        """
        print(f"Scraping Reddit post: {url}")

        try:
            submission = self.reddit.submission(url=url)
            submission._fetch()  # Load submission data

            comments = self._extract_all_comments(submission, limit=comment_limit)

            print(f"Found {len(comments)} comments")

            additional_data = {
                'post_title': submission.title,
                'post_author': str(submission.author) if submission.author else '[deleted]',
                'post_url': url,
                'post_score': submission.score,
                'post_created': normalize_timestamp(submission.created_utc),
                'subreddit': str(submission.subreddit),
                'num_comments': submission.num_comments,
            }

            output = create_output_structure(
                platform="reddit",
                product_query=url,
                comments=comments,
                additional_data=additional_data
            )

            return output

        except Exception as e:
            raise ScraperError(f"Failed to scrape Reddit post: {e}")

    def search_and_scrape(
        self,
        query: str,
        subreddit: Optional[str] = None,
        limit: int = 10,
        comment_limit: Optional[int] = None,
        time_filter: str = 'all',
        sort: str = 'relevance'
    ) -> Dict[str, Any]:
        """
        Search Reddit for posts about a product and scrape comments.

        Args:
            query: Search query (product name or keywords)
            subreddit: Specific subreddit to search (None for all Reddit)
            limit: Maximum number of posts to scrape
            comment_limit: Maximum comments per post
            time_filter: Time filter (all, day, week, month, year)
            sort: Sort method (relevance, hot, top, new, comments)

        Returns:
            Standardized output dictionary with all comments
        """
        print(f"Searching Reddit for: '{query}'")
        if subreddit:
            print(f"In subreddit: r/{subreddit}")

        try:
            # Search submissions
            if subreddit:
                search_results = self.reddit.subreddit(subreddit).search(
                    query,
                    limit=limit,
                    time_filter=time_filter,
                    sort=sort
                )
            else:
                search_results = self.reddit.subreddit('all').search(
                    query,
                    limit=limit,
                    time_filter=time_filter,
                    sort=sort
                )

            all_comments = []
            posts_scraped = 0

            for submission in search_results:
                posts_scraped += 1
                print(f"\nScraping post {posts_scraped}/{limit}: {submission.title[:60]}...")

                comments = self._extract_all_comments(submission, limit=comment_limit)
                print(f"  Found {len(comments)} comments")

                # Add post context to each comment
                for comment in comments:
                    comment['metadata']['post_title'] = submission.title
                    comment['metadata']['post_url'] = f"https://www.reddit.com{submission.permalink}"
                    comment['metadata']['subreddit'] = str(submission.subreddit)

                all_comments.extend(comments)

            print(f"\nTotal comments collected: {len(all_comments)}")

            additional_data = {
                'search_query': query,
                'subreddit': subreddit or 'all',
                'posts_scraped': posts_scraped,
                'time_filter': time_filter,
                'sort': sort,
            }

            output = create_output_structure(
                platform="reddit",
                product_query=query,
                comments=all_comments,
                additional_data=additional_data
            )

            return output

        except Exception as e:
            raise ScraperError(f"Failed to search/scrape Reddit: {e}")


def main():
    """Command-line interface for Reddit scraper."""
    parser = argparse.ArgumentParser(description="Scrape Reddit product discussions")
    parser.add_argument('--query', help='Search query (product name or keywords)')
    parser.add_argument('--url', help='Specific Reddit post URL to scrape')
    parser.add_argument('--subreddit', help='Specific subreddit to search in')
    parser.add_argument('--limit', type=int, default=10, help='Maximum number of posts to scrape')
    parser.add_argument('--comment-limit', type=int, help='Maximum comments per post (default: unlimited)')
    parser.add_argument('--time-filter', default='all', choices=['all', 'day', 'week', 'month', 'year'],
                        help='Time filter for search')
    parser.add_argument('--sort', default='relevance', choices=['relevance', 'hot', 'top', 'new', 'comments'],
                        help='Sort method for search results')
    parser.add_argument('--output', default='reddit_comments.json', help='Output JSON file')
    parser.add_argument('--client-id', help='Reddit API client ID (or set REDDIT_CLIENT_ID env var)')
    parser.add_argument('--client-secret', help='Reddit API client secret (or set REDDIT_CLIENT_SECRET env var)')
    parser.add_argument('--user-agent', help='User agent string')

    args = parser.parse_args()

    if not args.query and not args.url:
        parser.error("Either --query or --url must be specified")

    try:
        scraper = RedditScraper(
            client_id=args.client_id,
            client_secret=args.client_secret,
            user_agent=args.user_agent
        )

        if args.url:
            data = scraper.scrape_by_url(args.url, comment_limit=args.comment_limit)
        else:
            data = scraper.search_and_scrape(
                query=args.query,
                subreddit=args.subreddit,
                limit=args.limit,
                comment_limit=args.comment_limit,
                time_filter=args.time_filter,
                sort=args.sort
            )

        save_to_json(data, args.output)
        print(f"\nSuccessfully scraped {data['total_results']} comments!")

    except AuthenticationError as e:
        print(f"Authentication Error: {e}")
        print("\nTo use Reddit API:")
        print("1. Go to https://www.reddit.com/prefs/apps")
        print("2. Click 'Create App' or 'Create Another App'")
        print("3. Select 'script' type")
        print("4. Set redirect URI to http://localhost:8080")
        print("5. Use the client ID and secret in your .env file or as arguments")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
