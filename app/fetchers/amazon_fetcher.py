"""Amazon fetcher adapter for platform registry."""

from typing import Dict, Any
import structlog

from app.spapi.client import SPAPIClient

logger = structlog.get_logger(__name__)


class AmazonFetcher:
    """Adapter for Amazon SP-API client to match platform registry interface."""

    async def fetch_reviews(
        self,
        credentials: Dict[str, Any],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Fetch reviews from Amazon SP-API.

        Args:
            credentials: Dict with 'access_token', 'region', 'marketplace_id', 'seller_id'
            params: Dict with 'asins' (list), optional 'page_size', 'max_pages'

        Returns:
            Raw review data from SP-API

        Raises:
            SPAPIError: On API errors
        """
        access_token = credentials.get("access_token")
        region = credentials.get("region", "na")
        marketplace_id = credentials.get("marketplace_id")
        seller_id = credentials.get("seller_id")

        asins = params.get("asins", [])
        page_size = params.get("page_size", 100)
        max_pages = params.get("max_pages")

        if not access_token or not marketplace_id:
            raise ValueError("Credentials must include 'access_token' and 'marketplace_id'")

        if not asins:
            raise ValueError("Parameters must include 'asins' list")

        logger.info("fetching_amazon_reviews", seller_id=seller_id, asins_count=len(asins))

        # Create SP-API client
        client = SPAPIClient(region=region)

        # Collect all reviews for all ASINs
        all_reviews = []
        asin_results = {}

        for asin in asins:
            asin_reviews = []
            async for page_response in client.get_all_reviews(
                asin=asin,
                marketplace_id=marketplace_id,
                lwa_access_token=access_token,
                page_size=page_size,
                max_pages=max_pages,
            ):
                asin_reviews.extend(page_response.reviews)

            all_reviews.extend(asin_reviews)
            asin_results[asin] = {
                "reviews_count": len(asin_reviews),
                "reviews": asin_reviews,
            }

        logger.info("amazon_reviews_fetched", asins_count=len(asins), total_reviews=len(all_reviews))

        return {
            "platform": "amazon",
            "seller_id": seller_id,
            "marketplace_id": marketplace_id,
            "region": region,
            "asins": asins,
            "total_reviews": len(all_reviews),
            "asin_results": asin_results,
            "raw_reviews": all_reviews,
        }


# Global Amazon fetcher instance
amazon_fetcher = AmazonFetcher()
