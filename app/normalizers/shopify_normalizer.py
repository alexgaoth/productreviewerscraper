"""Normalizer for transforming Shopify review data to unified schema."""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional
import structlog

logger = structlog.get_logger(__name__)


class ShopifyNormalizer:
    """Normalizer for Shopify review data."""

    @staticmethod
    def normalize_review(
        metafield: Dict[str, Any],
        shop: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Normalize a single review from Shopify metafield to canonical format.

        Args:
            metafield: Raw metafield data from Shopify
            shop: Shop domain

        Returns:
            Normalized review dict or None if parsing fails
        """
        try:
            # Parse metafield value (usually JSON)
            value = metafield.get("value")
            if isinstance(value, str):
                try:
                    parsed_value = json.loads(value)
                except json.JSONDecodeError:
                    # Value might be plain text
                    parsed_value = {"body": value}
            else:
                parsed_value = value

            # Extract review data
            # Adjust field names based on your actual metafield structure
            return {
                "review_id": parsed_value.get("id") or parsed_value.get("review_id") or metafield.get("id"),
                "reviewer_id": parsed_value.get("reviewer_id") or parsed_value.get("customer_id"),
                "display_name": parsed_value.get("author_name") or parsed_value.get("name") or "Anonymous",
                "rating": parsed_value.get("rating") or parsed_value.get("stars") or parsed_value.get("score"),
                "title": parsed_value.get("title") or parsed_value.get("headline") or "",
                "body": parsed_value.get("body") or parsed_value.get("text") or parsed_value.get("content") or "",
                "verified_purchase": parsed_value.get("verified_purchase", parsed_value.get("verified", False)),
                "helpful_votes": parsed_value.get("helpful_votes") or parsed_value.get("upvotes") or 0,
                "language": parsed_value.get("language", "en"),
                "review_date": parsed_value.get("date") or parsed_value.get("created_at") or metafield.get("created_at"),
                "product_id": parsed_value.get("product_id") or metafield.get("owner_id"),
                "shop": shop,
                "platform": "shopify",
                "metafield_id": metafield.get("id"),
                "metafield_namespace": metafield.get("namespace"),
                "metafield_key": metafield.get("key"),
            }

        except Exception as e:
            logger.error("failed_to_normalize_shopify_review", metafield_id=metafield.get("id"), error=str(e))
            return None

    @staticmethod
    def create_normalized_artifact(
        job_id: str,
        shop_id: str,
        shop: str,
        reviews: List[Dict[str, Any]],
        raw_s3_keys: List[str],
        fetch_duration_seconds: float,
        namespace: str = "reviews",
    ) -> Dict[str, Any]:
        """
        Create canonical normalized JSON artifact for Shopify reviews.

        Args:
            job_id: Job ID
            shop_id: Shop identifier
            shop: Shop domain
            reviews: List of normalized reviews
            raw_s3_keys: List of S3 keys for raw data
            fetch_duration_seconds: Time taken to fetch
            namespace: Metafield namespace used

        Returns:
            Normalized artifact dict
        """
        fetched_at = datetime.utcnow().isoformat() + "Z"

        return {
            "job_id": job_id,
            "platform": "shopify",
            "shop_id": shop_id,
            "shop": shop,
            "fetched_at": fetched_at,
            "source": f"shopify_metafields_namespace_{namespace}",
            "raw_s3_paths": raw_s3_keys,
            "reviews_count": len(reviews),
            "reviews": reviews,
            "meta": {
                "namespace": namespace,
                "fetch_duration_seconds": round(fetch_duration_seconds, 2),
            },
        }

    def normalize(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for normalizing Shopify review data.

        This is the standardized interface that the platform registry expects.

        Args:
            raw_data: Raw data from Shopify fetcher

        Returns:
            Normalized data in unified schema
        """
        shop = raw_data.get("shop")
        namespace = raw_data.get("namespace", "reviews")
        metafields = raw_data.get("raw_metafields", [])

        logger.info("normalizing_shopify_reviews", shop=shop, metafields_count=len(metafields))

        normalized_reviews = []
        for metafield in metafields:
            normalized = self.normalize_review(metafield, shop)
            if normalized:
                normalized_reviews.append(normalized)

        logger.info("shopify_normalization_complete", shop=shop, reviews_count=len(normalized_reviews))

        return {
            "platform": "shopify",
            "shop": shop,
            "namespace": namespace,
            "reviews_count": len(normalized_reviews),
            "reviews": normalized_reviews,
        }


# Global Shopify normalizer instance
shopify_normalizer = ShopifyNormalizer()
