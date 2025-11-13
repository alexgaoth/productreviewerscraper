"""Login with Amazon (LWA) OAuth client."""

import secrets
import httpx
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


class LWATokenResponse:
    """Response from LWA token endpoint."""

    def __init__(self, data: Dict):
        self.access_token = data.get("access_token")
        self.refresh_token = data.get("refresh_token")  # Only in authorization_code grant
        self.token_type = data.get("token_type", "bearer")
        self.expires_in = data.get("expires_in", 3600)
        self.expires_at = datetime.utcnow() + timedelta(seconds=self.expires_in)

    def is_expired(self, buffer_seconds: int = 60) -> bool:
        """Check if token is expired or about to expire."""
        return datetime.utcnow() >= (self.expires_at - timedelta(seconds=buffer_seconds))


class LWAClient:
    """Client for Login with Amazon OAuth operations."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
    ):
        """Initialize LWA client."""
        self.client_id = client_id or settings.lwa_client_id
        self.client_secret = client_secret or settings.lwa_client_secret
        self.redirect_uri = redirect_uri or settings.lwa_redirect_uri
        self.token_url = settings.lwa_token_url
        self.authorization_url = settings.lwa_authorization_url

    def get_authorization_url(self, state: Optional[str] = None) -> Tuple[str, str]:
        """
        Generate authorization URL for OAuth flow.

        Args:
            state: Optional state parameter for CSRF protection

        Returns:
            Tuple of (authorization_url, state)
        """
        if not state:
            state = secrets.token_urlsafe(32)

        params = {
            "client_id": self.client_id,
            "scope": "profile postal_code",  # Add selling_partner_api.* if needed
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "state": state,
        }

        url = f"{self.authorization_url}?{urlencode(params)}"
        logger.info("generated_authorization_url", state=state)

        return url, state

    async def exchange_code_for_tokens(self, code: str) -> LWATokenResponse:
        """
        Exchange authorization code for access and refresh tokens.

        Args:
            code: Authorization code from callback

        Returns:
            LWATokenResponse with tokens

        Raises:
            httpx.HTTPError: If token exchange fails
        """
        logger.info("exchanging_authorization_code")

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if response.status_code != 200:
                error_data = response.json() if response.headers.get("content-type") == "application/json" else {}
                logger.error(
                    "token_exchange_failed",
                    status_code=response.status_code,
                    error=error_data,
                )
                response.raise_for_status()

            token_data = response.json()
            logger.info("token_exchange_success", expires_in=token_data.get("expires_in"))

            return LWATokenResponse(token_data)

    async def refresh_access_token(self, refresh_token: str) -> LWATokenResponse:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: Stored refresh token

        Returns:
            LWATokenResponse with new access token (and possibly new refresh token)

        Raises:
            httpx.HTTPError: If token refresh fails
        """
        logger.info("refreshing_access_token")

        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if response.status_code != 200:
                error_data = response.json() if response.headers.get("content-type") == "application/json" else {}
                logger.error(
                    "token_refresh_failed",
                    status_code=response.status_code,
                    error=error_data,
                )
                response.raise_for_status()

            token_data = response.json()
            logger.info("token_refresh_success", expires_in=token_data.get("expires_in"))

            return LWATokenResponse(token_data)


# Global LWA client instance
lwa_client = LWAClient()
