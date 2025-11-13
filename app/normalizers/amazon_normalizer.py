"""Amazon normalizer adapter for platform registry."""

from typing import Dict, Any
import structlog

from app.storage.normalizer import ReviewNormalizer

logger = structlog.get_logger(__name__)


class AmazonNormalizerAdapter:
    """Adapter for Amazon review normalizer to match platform registry interface."""

    def __init__(self):
        self.normalizer = ReviewNormalizer()

    def normalize(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize Amazon review data to unified schema.

        Args:
            raw_data: Raw data from Amazon fetcher

        Returns:
            Normalized data in unified schema
        """
        seller_id = raw_data.get("seller_id")
        marketplace_id = raw_data.get("marketplace_id")
        asin_results = raw_data.get("asin_results", {})

        logger.info("normalizing_amazon_reviews", seller_id=seller_id, asins_count=len(asin_results))

        all_normalized_reviews = []
        normalized_asins = {}

        for asin, asin_data in asin_results.items():
            reviews = asin_data.get("reviews", [])
            normalized_reviews = []

            for review in reviews:
                normalized = self.normalizer.normalize_review(
                    review=review,
                    asin=asin,
                    marketplace_id=marketplace_id,
                    page_token="",
                )
                normalized_reviews.append(normalized)

            all_normalized_reviews.extend(normalized_reviews)
            normalized_asins[asin] = {
                "reviews_count": len(normalized_reviews),
                "reviews": normalized_reviews,
            }

        logger.info("amazon_normalization_complete", seller_id=seller_id, total_reviews=len(all_normalized_reviews))

        return {
            "platform": "amazon",
            "seller_id": seller_id,
            "marketplace_id": marketplace_id,
            "reviews_count": len(all_normalized_reviews),
            "asin_results": normalized_asins,
            "reviews": all_normalized_reviews,
        }


# Global Amazon normalizer instance
amazon_normalizer = AmazonNormalizerAdapter()
