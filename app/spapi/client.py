"""Amazon Selling Partner API client for reviews."""

import httpx
from typing import Dict, List, Optional, AsyncIterator
from urllib.parse import urljoin, urlparse
import structlog

from app.config import settings
from app.spapi.signer import SigV4Signer, get_amz_date

logger = structlog.get_logger(__name__)


class SPAPIError(Exception):
    """Base exception for SP-API errors."""
    pass


class SPAPIAuthError(SPAPIError):
    """Authentication/authorization error (401, 403)."""
    pass


class SPAPIRateLimitError(SPAPIError):
    """Rate limit exceeded (429)."""

    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class SPAPIServerError(SPAPIError):
    """Server error (5xx)."""
    pass


class ReviewsResponse:
    """Response from reviews endpoint."""

    def __init__(self, data: Dict):
        self.raw_data = data
        self.reviews = data.get("reviews", [])
        self.next_token = data.get("nextToken") or data.get("pagination", {}).get("nextToken")

    def has_more_pages(self) -> bool:
        """Check if there are more pages."""
        return self.next_token is not None


class SPAPIClient:
    """Client for Amazon Selling Partner API."""

    # API endpoint version - adjust based on actual SP-API version
    # Note: The exact endpoint path may vary - check latest SP-API docs
    REVIEWS_API_VERSION = "v2024-06-01"  # TODO: Verify with latest SP-API docs

    def __init__(
        self,
        region: str = "na",
        aws_access_key: Optional[str] = None,
        aws_secret_key: Optional[str] = None,
    ):
        """
        Initialize SP-API client.

        Args:
            region: Region code (na, eu, fe)
            aws_access_key: AWS access key for SigV4
            aws_secret_key: AWS secret key for SigV4
        """
        self.region = region
        self.endpoint = settings.get_spapi_endpoint(region)

        # Extract AWS region from endpoint (e.g., us-east-1 for NA)
        region_map = {"na": "us-east-1", "eu": "eu-west-1", "fe": "us-west-2"}
        aws_region = region_map.get(region.lower(), "us-east-1")

        self.signer = SigV4Signer(
            access_key=aws_access_key or settings.spapi_aws_access_key_id,
            secret_key=aws_secret_key or settings.spapi_aws_secret_access_key,
            region=aws_region,
            service="execute-api",
        )

    def _get_base_headers(self, lwa_access_token: str) -> Dict[str, str]:
        """Get base headers for SP-API request."""
        parsed = urlparse(self.endpoint)
        amz_date = get_amz_date()

        return {
            "host": parsed.netloc,
            "x-amz-date": amz_date,
            "x-amz-access-token": lwa_access_token,  # LWA token
        }

    async def _make_request(
        self,
        method: str,
        path: str,
        lwa_access_token: str,
        params: Optional[Dict[str, str]] = None,
        data: Optional[str] = None,
    ) -> Dict:
        """
        Make signed SP-API request.

        Args:
            method: HTTP method
            path: API path
            lwa_access_token: LWA access token
            params: Query parameters
            data: Request body

        Returns:
            Response JSON

        Raises:
            SPAPIError: On API errors
        """
        url = urljoin(self.endpoint, path)

        # Prepare headers
        headers = self._get_base_headers(lwa_access_token)

        # Sign request
        signed_headers = self.signer.sign_request(
            method=method,
            url=url,
            headers=headers,
            payload=data or "",
            params=params,
        )

        logger.info(
            "making_spapi_request",
            method=method,
            path=path,
            params=params,
        )

        # Make request
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=signed_headers,
                params=params,
                content=data,
            )

            # Handle errors
            if response.status_code == 401 or response.status_code == 403:
                error_msg = f"Authentication failed: {response.status_code}"
                logger.error("spapi_auth_error", status=response.status_code, response=response.text)
                raise SPAPIAuthError(error_msg)

            elif response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                retry_after_int = int(retry_after) if retry_after else None
                error_msg = f"Rate limit exceeded. Retry after: {retry_after}"
                logger.warning("spapi_rate_limit", retry_after=retry_after)
                raise SPAPIRateLimitError(error_msg, retry_after=retry_after_int)

            elif response.status_code >= 500:
                error_msg = f"Server error: {response.status_code}"
                logger.error("spapi_server_error", status=response.status_code, response=response.text)
                raise SPAPIServerError(error_msg)

            elif response.status_code != 200:
                error_msg = f"Request failed: {response.status_code}"
                logger.error("spapi_request_failed", status=response.status_code, response=response.text)
                raise SPAPIError(error_msg)

            return response.json()

    async def get_reviews(
        self,
        asin: str,
        marketplace_id: str,
        lwa_access_token: str,
        page_size: int = 100,
        next_token: Optional[str] = None,
    ) -> ReviewsResponse:
        """
        Get reviews for an ASIN.

        Note: The exact endpoint path and parameters may vary.
        This implementation assumes a customer-feedback/reviews endpoint.
        Check the latest SP-API documentation for the correct endpoint.

        Args:
            asin: Product ASIN
            marketplace_id: Amazon marketplace ID
            lwa_access_token: Valid LWA access token
            page_size: Number of reviews per page
            next_token: Pagination token

        Returns:
            ReviewsResponse with reviews and pagination

        Raises:
            SPAPIError: On API errors
        """
        # TODO: Verify exact endpoint path with latest SP-API docs
        # This path is an example based on typical SP-API patterns
        path = f"/customer-feedback/{self.REVIEWS_API_VERSION}/asins/{asin}/reviews"

        params = {
            "marketplaceIds": marketplace_id,
            "pageSize": str(page_size),
        }

        if next_token:
            params["nextToken"] = next_token

        logger.info("fetching_reviews", asin=asin, marketplace_id=marketplace_id, has_next_token=bool(next_token))

        try:
            response_data = await self._make_request(
                method="GET",
                path=path,
                lwa_access_token=lwa_access_token,
                params=params,
            )

            logger.info(
                "reviews_fetched",
                asin=asin,
                reviews_count=len(response_data.get("reviews", [])),
                has_next=bool(response_data.get("nextToken")),
            )

            return ReviewsResponse(response_data)

        except SPAPIError:
            raise
        except Exception as e:
            logger.error("unexpected_error_fetching_reviews", asin=asin, error=str(e))
            raise SPAPIError(f"Unexpected error: {str(e)}")

    async def get_all_reviews(
        self,
        asin: str,
        marketplace_id: str,
        lwa_access_token: str,
        page_size: int = 100,
        max_pages: Optional[int] = None,
    ) -> AsyncIterator[ReviewsResponse]:
        """
        Get all reviews for an ASIN with pagination.

        Args:
            asin: Product ASIN
            marketplace_id: Amazon marketplace ID
            lwa_access_token: Valid LWA access token
            page_size: Number of reviews per page
            max_pages: Maximum pages to fetch (None for all)

        Yields:
            ReviewsResponse for each page

        Raises:
            SPAPIError: On API errors
        """
        next_token = None
        page_count = 0

        while True:
            # Check max pages limit
            if max_pages and page_count >= max_pages:
                logger.info("max_pages_reached", asin=asin, pages=page_count)
                break

            # Fetch page
            response = await self.get_reviews(
                asin=asin,
                marketplace_id=marketplace_id,
                lwa_access_token=lwa_access_token,
                page_size=page_size,
                next_token=next_token,
            )

            yield response

            page_count += 1

            # Check if more pages
            if not response.has_more_pages():
                logger.info("all_reviews_fetched", asin=asin, total_pages=page_count)
                break

            next_token = response.next_token
