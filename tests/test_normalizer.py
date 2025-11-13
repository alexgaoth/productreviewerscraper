"""Tests for review normalizer."""

import pytest
from app.storage.normalizer import normalizer


def test_normalize_review():
    """Test review normalization."""
    raw_review = {
        "reviewId": "R1TEST",
        "reviewerId": "A2REVIEWER",
        "reviewerName": "Test User",
        "rating": 5,
        "title": "Great product",
        "body": "This is a test review",
        "verifiedPurchase": True,
        "helpfulVotes": 10,
        "language": "en-US",
        "reviewDate": "2025-11-01T00:00:00Z",
    }

    normalized = normalizer.normalize_review(
        raw_review,
        asin="B07TEST",
        marketplace_id="ATVPDKIKX0DER",
        page_token="page1",
    )

    assert normalized["review_id"] == "R1TEST"
    assert normalized["reviewer_id"] == "A2REVIEWER"
    assert normalized["display_name"] == "Test User"
    assert normalized["rating"] == 5
    assert normalized["title"] == "Great product"
    assert normalized["body"] == "This is a test review"
    assert normalized["verified_purchase"] is True
    assert normalized["helpful_votes"] == 10
    assert normalized["language"] == "en-US"
    assert normalized["asin"] == "B07TEST"
    assert normalized["marketplace_id"] == "ATVPDKIKX0DER"
    assert normalized["fetched_from_raw_page"] == "page1"


def test_create_normalized_artifact():
    """Test normalized artifact creation."""
    reviews = [
        {
            "review_id": "R1TEST",
            "reviewer_id": "A2REVIEWER",
            "display_name": "Test User",
            "rating": 5,
            "title": "Great",
            "body": "Test",
            "verified_purchase": True,
            "helpful_votes": 10,
            "language": "en-US",
            "review_date": "2025-11-01",
            "asin": "B07TEST",
            "marketplace_id": "ATVPDKIKX0DER",
            "fetched_from_raw_page": "page1",
        }
    ]

    artifact = normalizer.create_normalized_artifact(
        job_id="job-123",
        seller_id="A1SELLER",
        marketplace_id="ATVPDKIKX0DER",
        asin="B07TEST",
        reviews=reviews,
        raw_s3_keys=["s3://bucket/raw/page1.json"],
        pages_fetched=1,
        next_token=None,
        fetch_duration_seconds=10.5,
    )

    assert artifact["job_id"] == "job-123"
    assert artifact["seller_id"] == "A1SELLER"
    assert artifact["marketplace_id"] == "ATVPDKIKX0DER"
    assert artifact["asin"] == "B07TEST"
    assert artifact["reviews_count"] == 1
    assert len(artifact["reviews"]) == 1
    assert artifact["meta"]["pages_fetched"] == 1
    assert artifact["meta"]["next_token"] is None
    assert artifact["meta"]["fetch_duration_seconds"] == 10.5
