"""
Common utilities for web scraping across platforms.
"""

import time
import random
from datetime import datetime
from typing import Dict, Any, List, Optional
import json

# User agents rotation for avoiding detection
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]


def get_random_user_agent() -> str:
    """Return a random user agent string."""
    return random.choice(USER_AGENTS)


def get_headers(custom_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """
    Generate headers for HTTP requests with random user agent.

    Args:
        custom_headers: Optional dictionary of custom headers to merge

    Returns:
        Dictionary of HTTP headers
    """
    headers = {
        'User-Agent': get_random_user_agent(),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    if custom_headers:
        headers.update(custom_headers)

    return headers


def delay(min_seconds: float = 1.0, max_seconds: float = 3.0):
    """
    Add a random delay between requests to avoid rate limiting.

    Args:
        min_seconds: Minimum delay in seconds
        max_seconds: Maximum delay in seconds
    """
    time.sleep(random.uniform(min_seconds, max_seconds))


def save_to_json(data: Dict[str, Any], filename: str):
    """
    Save scraped data to a JSON file.

    Args:
        data: Dictionary containing scraped data
        filename: Output filename
    """
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Data saved to {filename}")


def create_output_structure(
    platform: str,
    product_query: str,
    comments: List[Dict[str, Any]],
    additional_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create standardized output structure for scraped data.

    Args:
        platform: Name of the platform (e.g., 'reddit', 'amazon')
        product_query: Search term or URL used
        comments: List of comment/review dictionaries
        additional_data: Optional additional platform-specific data

    Returns:
        Standardized dictionary structure
    """
    output = {
        "platform": platform,
        "product_query": product_query,
        "scrape_timestamp": datetime.utcnow().isoformat() + "Z",
        "total_results": len(comments),
        "comments": comments
    }

    if additional_data:
        output.update(additional_data)

    return output


class RateLimitError(Exception):
    """Exception raised when rate limit is detected."""
    pass


class AuthenticationError(Exception):
    """Exception raised when authentication fails."""
    pass


class ScraperError(Exception):
    """Base exception for scraper errors."""
    pass


def handle_rate_limit(retry_after: int = 60):
    """
    Handle rate limit by waiting specified time.

    Args:
        retry_after: Seconds to wait before retrying
    """
    print(f"Rate limit detected. Waiting {retry_after} seconds...")
    time.sleep(retry_after)


def normalize_timestamp(timestamp: Any, format_str: Optional[str] = None) -> str:
    """
    Normalize various timestamp formats to ISO 8601.

    Args:
        timestamp: Timestamp in various formats
        format_str: Optional format string for parsing

    Returns:
        ISO 8601 formatted timestamp string
    """
    if isinstance(timestamp, datetime):
        return timestamp.isoformat() + "Z"

    if isinstance(timestamp, (int, float)):
        # Assume Unix timestamp
        return datetime.fromtimestamp(timestamp).isoformat() + "Z"

    if isinstance(timestamp, str):
        # Try to parse string timestamp
        if format_str:
            try:
                dt = datetime.strptime(timestamp, format_str)
                return dt.isoformat() + "Z"
            except ValueError:
                pass
        return timestamp

    return datetime.utcnow().isoformat() + "Z"
