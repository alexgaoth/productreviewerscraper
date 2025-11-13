"""Shopify fetcher for retrieving review data."""

import httpx
from typing import Dict, List, Optional, Any, AsyncIterator
from urllib.parse import urlencode
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


class ShopifyAPIError(Exception):
    """Base exception for Shopify API errors."""
    pass


class ShopifyAuthError(ShopifyAPIError):
    """Authentication/authorization error (401, 403)."""
    pass


class ShopifyRateLimitError(ShopifyAPIError):
    """Rate limit exceeded (429)."""

    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class ShopifyServerError(ShopifyAPIError):
    """Server error (5xx)."""
    pass


class ShopifyFetcher:
    """Fetcher for Shopify review data."""

    def __init__(self, api_version: Optional[str] = None):
        """
        Initialize Shopify fetcher.

        Args:
            api_version: Shopify API version (e.g., "2024-10")
        """
        self.api_version = api_version or settings.shopify_api_version

    def _get_api_url(self, shop: str, endpoint: str) -> str:
        """
        Get full API URL for an endpoint.

        Args:
            shop: Shop domain (e.g., "my-store.myshopify.com")
            endpoint: API endpoint path

        Returns:
            Full URL
        """
        # Ensure shop has proper format
        if not shop.endswith(".myshopify.com"):
            shop = f"{shop}.myshopify.com"

        return f"https://{shop}/admin/api/{self.api_version}/{endpoint}"

    async def _make_request(
        self,
        method: str,
        shop: str,
        endpoint: str,
        access_token: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make authenticated Shopify API request.

        Args:
            method: HTTP method
            shop: Shop domain
            endpoint: API endpoint
            access_token: Shopify access token
            params: Query parameters
            data: Request body (for POST/PUT)

        Returns:
            Response JSON

        Raises:
            ShopifyAPIError: On API errors
        """
        url = self._get_api_url(shop, endpoint)

        headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        }

        logger.info(
            "making_shopify_request",
            method=method,
            shop=shop,
            endpoint=endpoint,
            params=params,
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=data,
            )

            # Handle errors
            if response.status_code == 401 or response.status_code == 403:
                error_msg = f"Authentication failed: {response.status_code}"
                logger.error("shopify_auth_error", status=response.status_code, response=response.text)
                raise ShopifyAuthError(error_msg)

            elif response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                retry_after_int = int(retry_after) if retry_after else None
                error_msg = f"Rate limit exceeded. Retry after: {retry_after}"
                logger.warning("shopify_rate_limit", retry_after=retry_after)
                raise ShopifyRateLimitError(error_msg, retry_after=retry_after_int)

            elif response.status_code >= 500:
                error_msg = f"Server error: {response.status_code}"
                logger.error("shopify_server_error", status=response.status_code, response=response.text)
                raise ShopifyServerError(error_msg)

            elif response.status_code != 200:
                error_msg = f"Request failed: {response.status_code}"
                logger.error("shopify_request_failed", status=response.status_code, response=response.text)
                raise ShopifyAPIError(error_msg)

            return response.json()

    async def fetch_products(
        self,
        shop: str,
        access_token: str,
        limit: int = 250,
        page_info: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch products from Shopify.

        Args:
            shop: Shop domain
            access_token: Shopify access token
            limit: Number of products per page (max 250)
            page_info: Pagination cursor

        Returns:
            Response with products and pagination info

        Raises:
            ShopifyAPIError: On API errors
        """
        params = {"limit": min(limit, 250)}
        if page_info:
            params["page_info"] = page_info

        response = await self._make_request(
            method="GET",
            shop=shop,
            endpoint="products.json",
            access_token=access_token,
            params=params,
        )

        return response

    async def fetch_metafields(
        self,
        shop: str,
        access_token: str,
        owner_resource: str,
        owner_id: int,
        namespace: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch metafields for a resource.

        Args:
            shop: Shop domain
            access_token: Shopify access token
            owner_resource: Resource type (e.g., "product", "variant")
            owner_id: Resource ID
            namespace: Optional namespace filter (e.g., "reviews")

        Returns:
            List of metafields

        Raises:
            ShopifyAPIError: On API errors
        """
        endpoint = f"{owner_resource}s/{owner_id}/metafields.json"
        params = {}
        if namespace:
            params["namespace"] = namespace

        response = await self._make_request(
            method="GET",
            shop=shop,
            endpoint=endpoint,
            access_token=access_token,
            params=params,
        )

        return response.get("metafields", [])

    async def fetch_reviews_from_metafields(
        self,
        shop: str,
        access_token: str,
        product_ids: Optional[List[int]] = None,
        namespace: str = "reviews",
    ) -> Dict[str, Any]:
        """
        Fetch review data from product metafields.

        This assumes reviews are stored in metafields with a specific namespace.
        Customize the namespace and parsing logic based on your setup.

        Args:
            shop: Shop domain
            access_token: Shopify access token
            product_ids: Optional list of product IDs to fetch reviews for
            namespace: Metafield namespace for reviews

        Returns:
            Dict with shop info and review data

        Raises:
            ShopifyAPIError: On API errors
        """
        logger.info("fetching_reviews_from_metafields", shop=shop, namespace=namespace)

        all_reviews = []

        # If specific product IDs provided, fetch their metafields
        if product_ids:
            for product_id in product_ids:
                try:
                    metafields = await self.fetch_metafields(
                        shop=shop,
                        access_token=access_token,
                        owner_resource="product",
                        owner_id=product_id,
                        namespace=namespace,
                    )
                    all_reviews.extend(metafields)
                except ShopifyAPIError as e:
                    logger.error("failed_to_fetch_product_metafields", product_id=product_id, error=str(e))
                    continue
        else:
            # Fetch all products and their metafields
            # Note: This can be slow for large catalogs
            page_info = None
            products_fetched = 0

            while True:
                products_response = await self.fetch_products(
                    shop=shop,
                    access_token=access_token,
                    page_info=page_info,
                )

                products = products_response.get("products", [])
                if not products:
                    break

                products_fetched += len(products)
                logger.info("fetching_metafields_for_products", count=len(products), total=products_fetched)

                for product in products:
                    try:
                        metafields = await self.fetch_metafields(
                            shop=shop,
                            access_token=access_token,
                            owner_resource="product",
                            owner_id=product["id"],
                            namespace=namespace,
                        )
                        all_reviews.extend(metafields)
                    except ShopifyAPIError as e:
                        logger.error("failed_to_fetch_product_metafields", product_id=product["id"], error=str(e))
                        continue

                # Check for next page
                link_header = products_response.get("_link", None)
                if not link_header:
                    break

                # Parse page_info from Link header (simplified)
                # In production, parse the Link header properly
                page_info = None  # TODO: Implement proper Link header parsing
                break  # For now, only fetch first page to avoid rate limits

        logger.info("reviews_fetched_from_metafields", shop=shop, reviews_count=len(all_reviews))

        return {
            "platform": "shopify",
            "shop": shop,
            "namespace": namespace,
            "raw_metafields": all_reviews,
        }

    async def fetch_reviews(
        self,
        credentials: Dict[str, Any],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Main entry point for fetching reviews from Shopify.

        This is the standardized interface that the platform registry expects.

        Args:
            credentials: Dict with 'shop' and 'access_token'
            params: Dict with optional 'product_ids', 'namespace'

        Returns:
            Raw review data

        Raises:
            ShopifyAPIError: On API errors
        """
        shop = credentials.get("shop")
        access_token = credentials.get("access_token")

        if not shop or not access_token:
            raise ValueError("Credentials must include 'shop' and 'access_token'")

        product_ids = params.get("product_ids")
        namespace = params.get("namespace", "reviews")

        return await self.fetch_reviews_from_metafields(
            shop=shop,
            access_token=access_token,
            product_ids=product_ids,
            namespace=namespace,
        )


# Global Shopify fetcher instance
shopify_fetcher = ShopifyFetcher()
