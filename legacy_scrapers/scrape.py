#!/usr/bin/env python3
"""
Main entry point for product review scrapers.

This script provides a unified interface to all scrapers.

Usage:
    python scrape.py amazon --url "https://amazon.com/dp/..." --output reviews.json
    python scrape.py reddit --query "iPhone 15" --subreddit apple --output comments.json
    python scrape.py instagram --hashtag "tech" --max-posts 5
"""

import argparse
import sys
from scrapers.amazon_scraper import AmazonReviewScraper
from scrapers.reddit_scraper import RedditScraper
from scrapers.pinterest_scraper import PinterestScraper
from scrapers.instagram_scraper import InstagramScraper
from scrapers.facebook_scraper import FacebookScraper
from scrapers.tiktok_scraper import TikTokScraper
from scrapers.utils import save_to_json


def scrape_amazon(args):
    """Run Amazon scraper."""
    scraper = AmazonReviewScraper(args.url, max_pages=args.max_pages)
    data = scraper.scrape()
    save_to_json(data, args.output)
    print(f"\n✓ Successfully scraped {data['total_results']} Amazon reviews!")
    return 0


def scrape_reddit(args):
    """Run Reddit scraper."""
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
    print(f"\n✓ Successfully scraped {data['total_results']} Reddit comments!")
    return 0


def scrape_pinterest(args):
    """Run Pinterest scraper."""
    scraper = PinterestScraper(session_cookie=args.session_cookie)

    if args.pin_url:
        data = scraper.scrape_by_url(args.pin_url)
    else:
        data = scraper.scrape_by_search(args.query, max_pins=args.max_pins, max_comments_per_pin=args.max_comments)

    save_to_json(data, args.output)
    print(f"\n✓ Successfully scraped {data['total_results']} Pinterest comments!")
    return 0


def scrape_instagram(args):
    """Run Instagram scraper."""
    scraper = InstagramScraper(username=args.username, password=args.password)

    if args.post_url:
        data = scraper.scrape_by_url(args.post_url, max_comments=args.max_comments)
    elif args.hashtag:
        data = scraper.scrape_by_hashtag(args.hashtag, max_posts=args.max_posts, max_comments_per_post=args.max_comments)
    elif args.user:
        data = scraper.scrape_by_user(args.user, max_posts=args.max_posts, max_comments_per_post=args.max_comments)
    else:
        print("Error: Must specify --post-url, --hashtag, or --user")
        return 1

    save_to_json(data, args.output)
    print(f"\n✓ Successfully scraped {data['total_results']} Instagram comments!")
    return 0


def scrape_facebook(args):
    """Run Facebook scraper."""
    scraper = FacebookScraper(email=args.email, password=args.password)
    try:
        data = scraper.scrape_by_url(args.post_url, max_scrolls=args.max_scrolls)
        save_to_json(data, args.output)
        print(f"\n✓ Successfully scraped {data['total_results']} Facebook comments!")
        return 0
    finally:
        scraper.close()


def scrape_tiktok(args):
    """Run TikTok scraper."""
    use_api = args.use_api and not args.use_http
    scraper = TikTokScraper(use_api=use_api)

    if args.video_url:
        data = scraper.scrape_by_url(args.video_url, max_comments=args.max_comments)
    elif args.hashtag:
        data = scraper.scrape_by_hashtag(args.hashtag, max_videos=args.max_videos, max_comments_per_video=args.max_comments)
    elif args.user:
        data = scraper.scrape_by_user(args.user, max_videos=args.max_videos, max_comments_per_video=args.max_comments)
    else:
        print("Error: Must specify --video-url, --hashtag, or --user")
        return 1

    save_to_json(data, args.output)
    print(f"\n✓ Successfully scraped {data['total_results']} TikTok comments!")
    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Multi-platform product review scraper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Amazon
  python scrape.py amazon --url "https://amazon.com/dp/B0XXX" --max-pages 5

  # Reddit
  python scrape.py reddit --query "iPhone 15" --subreddit apple --limit 10

  # Instagram
  python scrape.py instagram --hashtag "iPhone15Pro" --max-posts 5

  # TikTok
  python scrape.py tiktok --hashtag "tech" --max-videos 10

For more help on a specific platform:
  python scrape.py amazon --help
  python scrape.py reddit --help
        """
    )

    subparsers = parser.add_subparsers(dest='platform', help='Platform to scrape')
    subparsers.required = True

    # Amazon scraper
    amazon_parser = subparsers.add_parser('amazon', help='Scrape Amazon reviews')
    amazon_parser.add_argument('--url', required=True, help='Amazon product URL')
    amazon_parser.add_argument('--max-pages', type=int, default=10, help='Maximum pages to scrape')
    amazon_parser.add_argument('--output', default='amazon_reviews.json', help='Output file')
    amazon_parser.set_defaults(func=scrape_amazon)

    # Reddit scraper
    reddit_parser = subparsers.add_parser('reddit', help='Scrape Reddit discussions')
    reddit_parser.add_argument('--query', help='Search query')
    reddit_parser.add_argument('--url', help='Specific post URL')
    reddit_parser.add_argument('--subreddit', help='Subreddit to search in')
    reddit_parser.add_argument('--limit', type=int, default=10, help='Max posts to scrape')
    reddit_parser.add_argument('--comment-limit', type=int, help='Max comments per post')
    reddit_parser.add_argument('--time-filter', default='all', choices=['all', 'day', 'week', 'month', 'year'])
    reddit_parser.add_argument('--sort', default='relevance', choices=['relevance', 'hot', 'top', 'new'])
    reddit_parser.add_argument('--client-id', help='Reddit client ID')
    reddit_parser.add_argument('--client-secret', help='Reddit client secret')
    reddit_parser.add_argument('--user-agent', help='User agent')
    reddit_parser.add_argument('--output', default='reddit_comments.json', help='Output file')
    reddit_parser.set_defaults(func=scrape_reddit)

    # Pinterest scraper
    pinterest_parser = subparsers.add_parser('pinterest', help='Scrape Pinterest comments')
    pinterest_parser.add_argument('--query', help='Search query')
    pinterest_parser.add_argument('--pin-url', help='Specific pin URL')
    pinterest_parser.add_argument('--max-pins', type=int, default=10, help='Max pins to scrape')
    pinterest_parser.add_argument('--max-comments', type=int, default=50, help='Max comments per pin')
    pinterest_parser.add_argument('--session-cookie', help='Pinterest session cookie')
    pinterest_parser.add_argument('--output', default='pinterest_comments.json', help='Output file')
    pinterest_parser.set_defaults(func=scrape_pinterest)

    # Instagram scraper
    instagram_parser = subparsers.add_parser('instagram', help='Scrape Instagram comments')
    instagram_parser.add_argument('--post-url', help='Specific post URL')
    instagram_parser.add_argument('--hashtag', help='Hashtag to search')
    instagram_parser.add_argument('--user', help='User to scrape')
    instagram_parser.add_argument('--max-posts', type=int, default=10, help='Max posts to scrape')
    instagram_parser.add_argument('--max-comments', type=int, help='Max comments per post')
    instagram_parser.add_argument('--username', help='Instagram username')
    instagram_parser.add_argument('--password', help='Instagram password')
    instagram_parser.add_argument('--output', default='instagram_comments.json', help='Output file')
    instagram_parser.set_defaults(func=scrape_instagram)

    # Facebook scraper
    facebook_parser = subparsers.add_parser('facebook', help='Scrape Facebook comments')
    facebook_parser.add_argument('--post-url', required=True, help='Facebook post URL')
    facebook_parser.add_argument('--max-scrolls', type=int, default=10, help='Max scrolls to load comments')
    facebook_parser.add_argument('--email', help='Facebook email')
    facebook_parser.add_argument('--password', help='Facebook password')
    facebook_parser.add_argument('--output', default='facebook_comments.json', help='Output file')
    facebook_parser.set_defaults(func=scrape_facebook)

    # TikTok scraper
    tiktok_parser = subparsers.add_parser('tiktok', help='Scrape TikTok comments')
    tiktok_parser.add_argument('--video-url', help='Specific video URL')
    tiktok_parser.add_argument('--hashtag', help='Hashtag to search')
    tiktok_parser.add_argument('--user', help='User to scrape')
    tiktok_parser.add_argument('--max-videos', type=int, default=10, help='Max videos to scrape')
    tiktok_parser.add_argument('--max-comments', type=int, help='Max comments per video')
    tiktok_parser.add_argument('--use-api', action='store_true', default=True, help='Use TikTokApi library')
    tiktok_parser.add_argument('--use-http', action='store_true', help='Use HTTP requests')
    tiktok_parser.add_argument('--output', default='tiktok_comments.json', help='Output file')
    tiktok_parser.set_defaults(func=scrape_tiktok)

    args = parser.parse_args()

    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user.")
        return 1
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
