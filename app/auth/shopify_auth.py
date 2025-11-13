"""Shopify OAuth 2.0 authentication client."""

import secrets
import httpx
from datetime import datetime
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


class ShopifyTokenResponse:
    """Response from Shopify OAuth token endpoint."""

    def __init__(self, data: Dict, shop: str):
        self.access_token = data.get("access_token")
        self.scope = data.get("scope")
        self.shop = shop
        # Shopify access tokens are long-lived and don't expire
        self.expires_at = None  # No expiration
        self.created_at = datetime.utcnow()

    def is_expired(self, buffer_seconds: int = 60) -> bool:
        """Shopify tokens don't expire - always return False."""
        return False


class ShopifyAuthClient:
    """Client for Shopify OAuth operations."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        api_version: Optional[str] = None,
        scopes: Optional[str] = None,
    ):
        """
        Initialize Shopify OAuth client.

        Args:
            client_id: Shopify app client ID
            client_secret: Shopify app client secret
            redirect_uri: OAuth redirect URI
            api_version: Shopify API version (e.g., "2024-10")
            scopes: Comma-separated list of scopes
        """
        self.client_id = client_id or settings.shopify_client_id
        self.client_secret = client_secret or settings.shopify_client_secret
        self.redirect_uri = redirect_uri or settings.shopify_redirect_uri
        self.api_version = api_version or settings.shopify_api_version
        self.scopes = scopes or settings.shopify_scopes

        if not self.client_id or not self.client_secret:
            raise ValueError("Shopify client_id and client_secret must be configured")

    def get_authorization_url(self, shop: str, state: Optional[str] = None) -> Tuple[str, str]:
        """
        Generate authorization URL for Shopify OAuth flow.

        Args:
            shop: Shop name (e.g., "my-store" or "my-store.myshopify.com")
            state: Optional state parameter for CSRF protection

        Returns:
            Tuple of (authorization_url, state)
        """
        if not state:
            state = secrets.token_urlsafe(32)

        # Ensure shop has proper format
        if not shop.endswith(".myshopify.com"):
            shop = f"{shop}.myshopify.com"

        params = {
            "client_id": self.client_id,
            "scope": self.scopes,
            "redirect_uri": self.redirect_uri,
            "state": state,
        }

        url = f"https://{shop}/admin/oauth/authorize?{urlencode(params)}"
        logger.info("generated_shopify_authorization_url", shop=shop, state=state)

        return url, state

    async def exchange_code_for_token(self, shop: str, code: str) -> ShopifyTokenResponse:
        """
        Exchange authorization code for permanent access token.

        Args:
            shop: Shop name (e.g., "my-store.myshopify.com")
            code: Authorization code from callback

        Returns:
            ShopifyTokenResponse with access token

        Raises:
            httpx.HTTPError: If token exchange fails
        """
        logger.info("exchanging_shopify_authorization_code", shop=shop)

        # Ensure shop has proper format
        if not shop.endswith(".myshopify.com"):
            shop = f"{shop}.myshopify.com"

        token_url = f"https://{shop}/admin/oauth/access_token"

        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                token_url,
                json=data,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code != 200:
                error_data = response.json() if response.headers.get("content-type") == "application/json" else {}
                logger.error(
                    "shopify_token_exchange_failed",
                    status_code=response.status_code,
                    error=error_data,
                    shop=shop,
                )
                response.raise_for_status()

            token_data = response.json()
            logger.info("shopify_token_exchange_success", shop=shop, scope=token_data.get("scope"))

            return ShopifyTokenResponse(token_data, shop)

    async def refresh_access_token(self, refresh_token: str) -> ShopifyTokenResponse:
        """
        Shopify doesn't use refresh tokens - tokens are long-lived.
        This method is kept for protocol compatibility.

        Args:
            refresh_token: Not used for Shopify

        Raises:
            NotImplementedError: Shopify doesn't support token refresh
        """
        raise NotImplementedError(
            "Shopify access tokens are long-lived and don't require refresh. "
            "If access is revoked, user must reauthorize."
        )

    async def verify_shop_domain(self, shop: str) -> bool:
        """
        Verify that a shop domain is valid.

        Args:
            shop: Shop name to verify

        Returns:
            True if shop exists, False otherwise
        """
        # Ensure shop has proper format
        if not shop.endswith(".myshopify.com"):
            shop = f"{shop}.myshopify.com"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Try to access the shop's public page
                response = await client.get(f"https://{shop}", follow_redirects=True)
                return response.status_code == 200
        except Exception as e:
            logger.warning("shop_verification_failed", shop=shop, error=str(e))
            return False


# Global Shopify auth client instance
shopify_auth_client = ShopifyAuthClient()
