# Setup Guide

Complete setup instructions for the Product Review Scraper Suite.

## Prerequisites

- Python 3.8 or higher
- pip package manager
- Git (optional, for cloning)

## Step-by-Step Installation

### 1. Get the Code

```bash
# Clone from GitHub
git clone https://github.com/yourusername/productreviewerscraper.git
cd productreviewerscraper

# OR download and extract the ZIP file
```

### 2. Create Virtual Environment (Recommended)

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
# On Linux/macOS:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 3. Install Python Dependencies

```bash
# Install all dependencies
pip install -r requirements.txt

# OR install selectively for specific platforms:

# For Amazon + Reddit only (recommended to start):
pip install requests beautifulsoup4 lxml praw

# For Instagram:
pip install instaloader

# For TikTok:
pip install TikTokApi playwright
playwright install chromium

# For Facebook (advanced):
pip install selenium
```

### 4. Install Browser Drivers

#### For Facebook Scraper (Selenium)

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install chromium-chromedriver
```

**macOS (with Homebrew):**
```bash
brew install chromedriver
```

**Windows:**
1. Download ChromeDriver from: https://chromedriver.chromium.org/
2. Extract and add to PATH
3. Or place in project directory

#### For TikTok Scraper (Playwright)

```bash
playwright install chromium
```

### 5. Configure Credentials

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials
nano .env  # or use any text editor
```

### 6. Set Up Platform Credentials

#### Reddit (Required for Reddit scraper)

1. Go to https://www.reddit.com/prefs/apps
2. Click "Create App" or "Create Another App"
3. Fill in the form:
   - **Name**: ProductReviewScraper
   - **Type**: Select "script"
   - **Description**: (optional)
   - **About URL**: (leave blank)
   - **Redirect URI**: http://localhost:8080
4. Click "Create app"
5. Copy the credentials:
   - Client ID: under the app name (looks like: `a1b2c3d4e5f6g7`)
   - Client Secret: shown in the form
6. Add to `.env`:
   ```
   REDDIT_CLIENT_ID=your_client_id_here
   REDDIT_CLIENT_SECRET=your_client_secret_here
   REDDIT_USER_AGENT=ProductReviewScraper/1.0 by /u/yourusername
   ```

#### Instagram (Required for Instagram scraper)

1. Use your regular Instagram credentials
2. **IMPORTANT**: Consider creating a test account, as Instagram may flag scraping activity
3. Add to `.env`:
   ```
   INSTAGRAM_USERNAME=your_username
   INSTAGRAM_PASSWORD=your_password
   ```

#### Facebook (Required for Facebook scraper)

⚠️ **Warning**: Facebook actively bans accounts used for scraping. Use at your own risk.

1. Use your regular Facebook credentials OR create a test account
2. Add to `.env`:
   ```
   FACEBOOK_EMAIL=your_email@example.com
   FACEBOOK_PASSWORD=your_password
   ```

#### Pinterest (Optional for Pinterest scraper)

1. Login to Pinterest in your browser
2. Open Developer Tools (F12)
3. Go to Application → Cookies
4. Find `_pinterest_sess` cookie and copy its value
5. Add to `.env`:
   ```
   PINTEREST_SESSION_COOKIE=your_cookie_value
   ```

#### TikTok (No credentials needed)

TikTok scraper doesn't require authentication for basic usage.

### 7. Verify Installation

```bash
# Test Amazon scraper (no auth required)
python -m scrapers.amazon_scraper --help

# Test Reddit scraper (requires auth)
python -m scrapers.reddit_scraper --help

# Test the unified interface
python scrape.py --help
```

## Quick Test

### Test Amazon Scraper

```bash
python scrape.py amazon \
  --url "https://www.amazon.com/dp/B0BSHF7WHW" \
  --max-pages 2 \
  --output test_amazon.json
```

### Test Reddit Scraper

```bash
python scrape.py reddit \
  --query "iPhone review" \
  --subreddit "apple" \
  --limit 3 \
  --output test_reddit.json
```

## Troubleshooting

### "Module not found" error

```bash
# Make sure you're in the project directory
cd productreviewerscraper

# Reinstall dependencies
pip install -r requirements.txt
```

### Reddit authentication fails

- Verify credentials in `.env` are correct
- Check that redirect URI is exactly: `http://localhost:8080`
- Ensure no extra spaces in `.env` file
- Try regenerating the client secret on Reddit

### ChromeDriver version mismatch

```bash
# Check Chrome version
google-chrome --version  # Linux
# or
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --version  # macOS

# Install matching ChromeDriver version
# Download from: https://chromedriver.chromium.org/downloads
```

### Instagram login fails

- Check username/password are correct
- If you have 2FA enabled, you may need to:
  - Temporarily disable it, OR
  - Approve login from email/phone
- Instagram may require CAPTCHA - run in non-headless mode to solve manually

### TikTok API errors

```bash
# Reinstall TikTok dependencies
pip uninstall TikTokApi playwright
pip install TikTokApi playwright
playwright install chromium
```

### Permission denied on Linux

```bash
# Make scrape.py executable
chmod +x scrape.py

# Run with python explicitly
python3 scrape.py amazon --help
```

## Platform-Specific Notes

### Amazon
- ✅ No authentication required
- ✅ Generally reliable
- ⚠️ May show CAPTCHA with heavy usage
- 💡 Use delays between requests (built-in)

### Reddit
- ✅ Official API (most reliable)
- ✅ Well-documented
- ✅ Free tier available
- 💡 Rate limits: 60 requests/minute

### Instagram
- ⚠️ Unofficial library (may break)
- ⚠️ Requires login
- ⚠️ May trigger account warnings
- 💡 Use test account for safety

### Facebook
- ⚠️ Very difficult to scrape
- ⚠️ High risk of account ban
- ⚠️ Frequently changes structure
- 💡 Consider official Graph API instead

### TikTok
- ⚠️ Unofficial library (may break)
- ✅ No login required
- ⚠️ API structure changes frequently
- 💡 HTTP fallback available

### Pinterest
- ⚠️ Strict anti-scraping measures
- ⚠️ Requires session cookie
- ⚠️ May not work without proxies
- 💡 Consider official API for production

## Next Steps

1. **Start with Amazon and Reddit** - they're the most reliable
2. **Test with small limits** before scaling up
3. **Monitor for errors** and adjust delays if needed
4. **Read platform ToS** before large-scale scraping
5. **Consider official APIs** for production use

## Getting Help

- Check README.md for usage examples
- Review examples/example_usage.py
- Open an issue on GitHub
- Read troubleshooting section above

## Security Best Practices

1. **Never commit `.env` file** to version control
2. **Use test accounts** for social platforms
3. **Don't share credentials** in issues or pull requests
4. **Rotate credentials** if compromised
5. **Use environment variables** in production

## License Compliance

- Review each platform's Terms of Service
- Respect robots.txt files
- Don't exceed rate limits
- Use for personal/research purposes
- Consider official APIs for commercial use
