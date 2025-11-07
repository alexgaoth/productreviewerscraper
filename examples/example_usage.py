"""
Example usage of the product review scrapers.

This file demonstrates how to use each scraper programmatically.
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.amazon_scraper import AmazonReviewScraper
from scrapers.reddit_scraper import RedditScraper
from scrapers.instagram_scraper import InstagramScraper
from scrapers.tiktok_scraper import TikTokScraper
from scrapers.utils import save_to_json


def example_amazon():
    """Example: Scrape Amazon product reviews."""
    print("=" * 60)
    print("AMAZON EXAMPLE")
    print("=" * 60)

    # Initialize scraper with product URL
    scraper = AmazonReviewScraper(
        product_url="https://www.amazon.com/dp/B0BSHF7WHW",  # Example: Apple AirPods Pro
        max_pages=3  # Scrape first 3 pages
    )

    # Scrape reviews
    data = scraper.scrape()

    # Save to file
    save_to_json(data, 'examples/amazon_example_output.json')

    # Print summary
    print(f"\nScraped {data['total_results']} reviews")
    print(f"First review: {data['comments'][0]['text'][:100]}...")
    print(f"Average rating: {sum(c['rating'] for c in data['comments'] if c['rating']) / len([c for c in data['comments'] if c['rating']]):.2f}")


def example_reddit():
    """Example: Search Reddit for product discussions."""
    print("\n" + "=" * 60)
    print("REDDIT EXAMPLE")
    print("=" * 60)

    try:
        # Initialize scraper with API credentials
        scraper = RedditScraper()

        # Search for product discussions
        data = scraper.search_and_scrape(
            query="AirPods Pro review",
            subreddit="apple",  # Search in r/apple
            limit=5,  # Get 5 posts
            comment_limit=20,  # Get up to 20 comments per post
            time_filter='month',  # Posts from last month
            sort='top'  # Top posts
        )

        # Save to file
        save_to_json(data, 'examples/reddit_example_output.json')

        # Print summary
        print(f"\nScraped {data['total_results']} comments from {data['posts_scraped']} posts")
        if data['comments']:
            print(f"First comment: {data['comments'][0]['text'][:100]}...")

    except Exception as e:
        print(f"Error: {e}")
        print("Make sure to set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in .env")


def example_instagram():
    """Example: Scrape Instagram post comments."""
    print("\n" + "=" * 60)
    print("INSTAGRAM EXAMPLE")
    print("=" * 60)

    try:
        # Initialize scraper
        scraper = InstagramScraper()

        # Scrape comments from a specific post
        data = scraper.scrape_by_url(
            post_url="https://www.instagram.com/p/C1234567890/",  # Replace with real post URL
            max_comments=50
        )

        # Save to file
        save_to_json(data, 'examples/instagram_example_output.json')

        # Print summary
        print(f"\nScraped {data['total_results']} comments")
        if data['comments']:
            print(f"First comment: {data['comments'][0]['text'][:100]}...")

    except Exception as e:
        print(f"Error: {e}")
        print("Make sure to set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD in .env")


def example_tiktok():
    """Example: Scrape TikTok video comments."""
    print("\n" + "=" * 60)
    print("TIKTOK EXAMPLE")
    print("=" * 60)

    try:
        # Initialize scraper
        scraper = TikTokScraper(use_api=True)

        # Scrape comments from a video
        data = scraper.scrape_by_url(
            video_url="https://www.tiktok.com/@apple/video/1234567890",  # Replace with real video URL
            max_comments=100
        )

        # Save to file
        save_to_json(data, 'examples/tiktok_example_output.json')

        # Print summary
        print(f"\nScraped {data['total_results']} comments")
        if data['comments']:
            print(f"First comment: {data['comments'][0]['text'][:100]}...")

    except Exception as e:
        print(f"Error: {e}")
        print("Make sure TikTokApi and playwright are installed")


def example_data_analysis():
    """Example: Analyze scraped data."""
    print("\n" + "=" * 60)
    print("DATA ANALYSIS EXAMPLE")
    print("=" * 60)

    import json
    from collections import Counter

    # Load scraped data (assuming amazon example was run)
    try:
        with open('examples/amazon_example_output.json', 'r') as f:
            data = json.load(f)

        comments = data['comments']

        # Calculate statistics
        total_comments = len(comments)
        total_likes = sum(c['likes'] for c in comments)
        avg_likes = total_likes / total_comments if total_comments > 0 else 0

        # Rating distribution
        ratings = [c['rating'] for c in comments if c['rating'] is not None]
        rating_dist = Counter(ratings)

        # Most helpful comments
        top_comments = sorted(comments, key=lambda x: x['likes'], reverse=True)[:5]

        # Print analysis
        print(f"\nTotal comments: {total_comments}")
        print(f"Total likes: {total_likes}")
        print(f"Average likes per comment: {avg_likes:.2f}")
        print(f"\nRating distribution:")
        for rating, count in sorted(rating_dist.items(), reverse=True):
            print(f"  {rating} stars: {count} ({count/len(ratings)*100:.1f}%)")

        print(f"\nTop 5 most helpful comments:")
        for i, comment in enumerate(top_comments, 1):
            print(f"  {i}. [{comment['likes']} likes] {comment['text'][:80]}...")

    except FileNotFoundError:
        print("No data file found. Run example_amazon() first.")
    except Exception as e:
        print(f"Error analyzing data: {e}")


def example_multi_platform_comparison():
    """Example: Compare sentiment across platforms."""
    print("\n" + "=" * 60)
    print("MULTI-PLATFORM COMPARISON")
    print("=" * 60)

    # This would combine data from multiple platforms
    # and perform comparative analysis

    platforms_data = {}

    # Load data from each platform
    for platform in ['amazon', 'reddit', 'instagram', 'tiktok']:
        filename = f'examples/{platform}_example_output.json'
        try:
            import json
            with open(filename, 'r') as f:
                platforms_data[platform] = json.load(f)
        except FileNotFoundError:
            print(f"No data for {platform}")
            continue

    # Compare metrics
    print("\nPlatform comparison:")
    for platform, data in platforms_data.items():
        total = data['total_results']
        avg_likes = sum(c['likes'] for c in data['comments']) / total if total > 0 else 0
        print(f"\n{platform.upper()}:")
        print(f"  Total comments: {total}")
        print(f"  Avg engagement: {avg_likes:.2f}")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Run example scrapers')
    parser.add_argument('--amazon', action='store_true', help='Run Amazon example')
    parser.add_argument('--reddit', action='store_true', help='Run Reddit example')
    parser.add_argument('--instagram', action='store_true', help='Run Instagram example')
    parser.add_argument('--tiktok', action='store_true', help='Run TikTok example')
    parser.add_argument('--analyze', action='store_true', help='Run data analysis example')
    parser.add_argument('--compare', action='store_true', help='Run multi-platform comparison')
    parser.add_argument('--all', action='store_true', help='Run all examples')

    args = parser.parse_args()

    # Create examples directory if it doesn't exist
    os.makedirs('examples', exist_ok=True)

    if args.all or args.amazon:
        try:
            example_amazon()
        except Exception as e:
            print(f"Amazon example failed: {e}")

    if args.all or args.reddit:
        try:
            example_reddit()
        except Exception as e:
            print(f"Reddit example failed: {e}")

    if args.all or args.instagram:
        try:
            example_instagram()
        except Exception as e:
            print(f"Instagram example failed: {e}")

    if args.all or args.tiktok:
        try:
            example_tiktok()
        except Exception as e:
            print(f"TikTok example failed: {e}")

    if args.analyze:
        example_data_analysis()

    if args.compare:
        example_multi_platform_comparison()

    if not any(vars(args).values()):
        parser.print_help()
