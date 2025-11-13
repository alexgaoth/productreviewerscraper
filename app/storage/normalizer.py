"""Normalizer for transforming raw SP-API responses to canonical format."""

from datetime import datetime
from typing import Dict, Any, List, Optional
import structlog

logger = structlog.get_logger(__name__)


class ReviewNormalizer:
    """Normalizer for review data."""

    @staticmethod
    def normalize_review(review: Dict[str, Any], asin: str, marketplace_id: str, page_token: str) -> Dict[str, Any]:
        """
        Normalize a single review to canonical format.

        Args:
            review: Raw review data from SP-API
            asin: Product ASIN
            marketplace_id: Marketplace ID
            page_token: Source page identifier

        Returns:
            Normalized review dict
        """
        # Note: Field names may vary based on actual SP-API response
        # Adjust based on real API response structure
        return {
            "review_id": review.get("reviewId") or review.get("id"),
            "reviewer_id": review.get("reviewerId"),
            "display_name": review.get("reviewerName") or review.get("displayName"),
            "rating": review.get("rating") or review.get("stars"),
            "title": review.get("title") or review.get("headline"),
            "body": review.get("body") or review.get("text") or review.get("content"),
            "verified_purchase": review.get("verifiedPurchase", False),
            "helpful_votes": review.get("helpfulVotes", 0),
            "language": review.get("language", "en-US"),
            "review_date": review.get("reviewDate") or review.get("date"),
            "asin": asin,
            "marketplace_id": marketplace_id,
            "fetched_from_raw_page": page_token,
        }

    @staticmethod
    def create_normalized_artifact(
        job_id: str,
        seller_id: str,
        marketplace_id: str,
        asin: str,
        reviews: List[Dict[str, Any]],
        raw_s3_keys: List[str],
        pages_fetched: int,
        next_token: Optional[str],
        fetch_duration_seconds: float,
        source_endpoint: str = "customer-feedback/v2024-06-01/asins/{asin}/reviews",
    ) -> Dict[str, Any]:
        """
        Create canonical normalized JSON artifact.

        Args:
            job_id: Job ID
            seller_id: Seller ID
            marketplace_id: Marketplace ID
            asin: Product ASIN
            reviews: List of normalized reviews
            raw_s3_keys: List of S3 keys for raw pages
            pages_fetched: Number of pages fetched
            next_token: Next pagination token (if any)
            fetch_duration_seconds: Time taken to fetch
            source_endpoint: SP-API endpoint path

        Returns:
            Normalized artifact dict
        """
        fetched_at = datetime.utcnow().isoformat() + "Z"

        return {
            "job_id": job_id,
            "seller_id": seller_id,
            "marketplace_id": marketplace_id,
            "asin": asin,
            "fetched_at": fetched_at,
            "source_endpoint": source_endpoint.format(asin=asin),
            "raw_s3_paths": raw_s3_keys,
            "reviews_count": len(reviews),
            "reviews": reviews,
            "meta": {
                "pages_fetched": pages_fetched,
                "next_token": next_token,
                "fetch_duration_seconds": round(fetch_duration_seconds, 2),
            },
        }


# Global normalizer instance
normalizer = ReviewNormalizer()
