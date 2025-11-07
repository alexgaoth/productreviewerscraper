# Product Review Scraper Suite

A comprehensive collection of web scrapers for collecting product reviews and comments from multiple platforms: **Amazon, Reddit, Pinterest, Facebook, Instagram, and TikTok**.

## Features

- ✅ **Multi-platform support**: 6 major platforms covered
- ✅ **Standardized JSON output**: All scrapers output normalized data format
- ✅ **Rich metadata extraction**: Captures usernames, timestamps, likes, replies, and more
- ✅ **Pagination support**: Retrieves as many comments as possible
- ✅ **Rate limiting protection**: Built-in delays to avoid getting blocked
- ✅ **Error handling**: Robust error handling for rate limits and authentication
- ✅ **Modular design**: Each scraper works independently

## Supported Platforms

| Platform | Scraping Method | Authentication Required | Difficulty |
|----------|----------------|------------------------|------------|
| **Amazon** | HTTP + BeautifulSoup | No | Easy |
| **Reddit** | Official API (PRAW) | Yes (API keys) | Easy |
| **Pinterest** | HTTP + API endpoints | Optional | Medium |
| **Facebook** | Selenium | Yes | Hard |
| **Instagram** | instaloader library | Yes | Medium |
| **TikTok** | TikTokApi library | No | Medium |

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/productreviewerscraper.git
cd productreviewerscraper
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Install browser drivers (for Selenium-based scrapers)

For Facebook scraper:
```bash
# Install ChromeDriver
# Linux:
apt-get install chromium-chromedriver

# macOS:
brew install chromedriver

# Windows: Download from https://chromedriver.chromium.org/
```

For TikTok scraper (if using TikTokApi):
```bash
playwright install chromium
```

### 4. Configure credentials

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
# Edit .env with your credentials
```

## Quick Start

### Amazon Reviews

Scrape product reviews from Amazon:

```bash
python -m scrapers.amazon_scraper \
  --url "https://www.amazon.com/dp/B0XXXXXX" \
  --max-pages 5 \
  --output amazon_reviews.json
```

### Reddit Discussions

Search Reddit for product discussions:

```bash
python -m scrapers.reddit_scraper \
  --query "iPhone 15 Pro review" \
  --subreddit "apple" \
  --limit 20 \
  --output reddit_comments.json
```

Or scrape a specific post:

```bash
python -m scrapers.reddit_scraper \
  --url "https://www.reddit.com/r/apple/comments/..." \
  --output reddit_comments.json
```

### Pinterest Comments

```bash
python -m scrapers.pinterest_scraper \
  --query "iPhone 15 Pro" \
  --max-pins 10 \
  --output pinterest_comments.json
```

### Instagram Comments

Scrape comments from a specific post:

```bash
python -m scrapers.instagram_scraper \
  --post-url "https://www.instagram.com/p/ABC123/" \
  --max-comments 100 \
  --output instagram_comments.json
```

Search by hashtag:

```bash
python -m scrapers.instagram_scraper \
  --hashtag "iPhone15Pro" \
  --max-posts 10 \
  --output instagram_comments.json
```

### Facebook Comments

```bash
python -m scrapers.facebook_scraper \
  --post-url "https://www.facebook.com/permalink.php?story_fbid=..." \
  --max-scrolls 10 \
  --output facebook_comments.json
```

### TikTok Comments

Scrape comments from a video:

```bash
python -m scrapers.tiktok_scraper \
  --video-url "https://www.tiktok.com/@user/video/123456789" \
  --max-comments 200 \
  --output tiktok_comments.json
```

Search by hashtag:

```bash
python -m scrapers.tiktok_scraper \
  --hashtag "iPhone15Pro" \
  --max-videos 10 \
  --output tiktok_comments.json
```

## Output Format

All scrapers produce standardized JSON output:

```json
{
  "platform": "reddit",
  "product_query": "iPhone 15 Pro review",
  "scrape_timestamp": "2024-01-15T10:30:45Z",
  "total_results": 150,
  "comments": [
    {
      "id": "abc123",
      "text": "This product is amazing!",
      "author": "username",
      "timestamp": "2024-01-14T15:20:30Z",
      "likes": 42,
      "replies": 3,
      "rating": 5.0,
      "profile_link": "https://...",
      "verified_status": false,
      "metadata": {
        "platform_specific_field": "value"
      }
    }
  ]
}
```

## Authentication Setup

### Reddit

1. Go to https://www.reddit.com/prefs/apps
2. Click "Create App" or "Create Another App"
3. Select "script" type
4. Set redirect URI to `http://localhost:8080`
5. Copy client ID and secret to `.env`

### Instagram

Use your regular Instagram credentials in `.env`:

```
INSTAGRAM_USERNAME=your_username
INSTAGRAM_PASSWORD=your_password
```

**Warning**: Instagram may flag accounts that scrape extensively. Consider using a test account.

### Facebook

Use your regular Facebook credentials in `.env`:

```
FACEBOOK_EMAIL=your_email
FACEBOOK_PASSWORD=your_password
```

**Warning**: Facebook actively bans accounts used for scraping. Use at your own risk. Consider the official Graph API instead.

### Pinterest

1. Login to Pinterest in your browser
2. Open Developer Tools (F12)
3. Go to Application/Storage → Cookies
4. Copy the value of `_pinterest_sess` cookie
5. Add to `.env`

## API Documentation

### Common Parameters

All scrapers support these common patterns:

- `--output`: Output JSON filename (default varies by scraper)
- `--max-*`: Limits for pages/posts/comments to scrape
- Platform-specific authentication flags

### Platform-Specific Features

#### Amazon
- Handles pagination automatically
- Extracts verified purchase status
- Captures review images
- No authentication required

#### Reddit
- Uses official PRAW library
- Supports subreddit filtering
- Time-based filtering (day, week, month, year)
- Sorting options (relevance, hot, top, new)

#### Instagram
- Search by hashtag or user profile
- Extracts post metadata
- Requires login for most operations

#### TikTok
- Search by hashtag or user
- Extracts video metadata
- Two modes: API library or HTTP requests

## Rate Limiting & Best Practices

### Delays Between Requests

All scrapers implement automatic delays:
- Amazon: 2-4 seconds between pages
- Reddit: 1-2 seconds (API has built-in rate limiting)
- Instagram: 3-5 seconds between posts
- TikTok: 2-4 seconds between videos
- Pinterest/Facebook: 1-4 seconds

### Avoiding Bans

1. **Use proxies** for high-volume scraping
2. **Rotate user agents** (built into scrapers)
3. **Respect rate limits** (don't override delays)
4. **Use official APIs** when available (Reddit)
5. **Don't scrape during peak hours**
6. **Use test accounts** for social platforms

### Legal & Ethical Considerations

⚠️ **Important Warnings**:

- **Terms of Service**: Most platforms prohibit scraping in their ToS
- **Legal risks**: Scraping may violate CFAA or similar laws in some jurisdictions
- **Account bans**: Aggressive scraping can result in account termination
- **Rate limits**: Exceeding rate limits may result in IP bans

**Recommended for**:
- Personal research
- Academic studies
- Authorized security testing
- Small-scale data collection

**Not recommended for**:
- Commercial data resale
- Large-scale automated scraping
- Bypassing API restrictions
- Impersonation or spam

### Official API Alternatives

For production use, consider official APIs:

- **Reddit**: https://www.reddit.com/dev/api
- **Instagram**: https://developers.facebook.com/docs/instagram-api
- **Facebook**: https://developers.facebook.com/docs/graph-api
- **TikTok**: https://developers.tiktok.com/products/research-api
- **Pinterest**: https://developers.pinterest.com

## Troubleshooting

### Common Issues

#### "Module not found" errors
```bash
pip install -r requirements.txt
```

#### Reddit authentication fails
- Check client ID and secret are correct
- Ensure redirect URI matches exactly
- Verify user agent is set

#### Instagram/Facebook login fails
- Check username/password are correct
- Disable 2FA or handle manually in browser
- Instagram may require you to verify login from email

#### ChromeDriver errors (Facebook scraper)
```bash
# Update ChromeDriver to match your Chrome version
# Linux:
apt-get update && apt-get install chromium-chromedriver

# macOS:
brew upgrade chromedriver
```

#### TikTok API errors
```bash
# Reinstall playwright browsers
playwright install chromium
```

#### Rate limiting / IP bans
- Increase delays between requests
- Use proxies
- Switch to official APIs
- Wait 24-48 hours before retrying

## Project Structure

```
productreviewerscraper/
├── scrapers/
│   ├── __init__.py
│   ├── utils.py              # Common utilities
│   ├── amazon_scraper.py     # Amazon reviews
│   ├── reddit_scraper.py     # Reddit discussions
│   ├── pinterest_scraper.py  # Pinterest comments
│   ├── instagram_scraper.py  # Instagram comments
│   ├── facebook_scraper.py   # Facebook comments
│   └── tiktok_scraper.py     # TikTok comments
├── examples/                  # Usage examples
├── .env.example              # Environment variables template
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

## Advanced Usage

### Using Scrapers Programmatically

```python
from scrapers.amazon_scraper import AmazonReviewScraper
from scrapers.utils import save_to_json

# Initialize scraper
scraper = AmazonReviewScraper(
    product_url="https://www.amazon.com/dp/B0XXXXX",
    max_pages=5
)

# Scrape reviews
data = scraper.scrape()

# Save to file
save_to_json(data, 'output.json')

# Access individual reviews
for review in data['comments']:
    print(f"{review['author']}: {review['text'][:100]}")
    print(f"Rating: {review['rating']}, Likes: {review['likes']}")
```

### Custom Processing

```python
import json

# Load scraped data
with open('amazon_reviews.json', 'r') as f:
    data = json.load(f)

# Filter 5-star reviews
five_star = [
    r for r in data['comments']
    if r['rating'] == 5.0
]

# Calculate average likes
avg_likes = sum(r['likes'] for r in data['comments']) / len(data['comments'])

# Find most helpful review
most_helpful = max(data['comments'], key=lambda r: r['likes'])
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request

## Disclaimer

This software is provided for educational and research purposes only. Users are responsible for:

- Complying with all applicable laws and regulations
- Respecting platform Terms of Service
- Obtaining necessary permissions for data collection
- Using the software ethically and responsibly

The authors assume no liability for misuse of this software.

## License

MIT License - see LICENSE file for details

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Check existing issues for solutions
- Read the troubleshooting section above

---

**Remember**: Always respect robots.txt, rate limits, and Terms of Service. When in doubt, use official APIs.
