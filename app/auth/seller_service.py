"""Service for managing seller tokens and authentication."""

from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
import structlog

from app.models import Seller, SellerStatus
from app.crypto import encrypt_refresh_token, decrypt_refresh_token
from app.auth.lwa_client import lwa_client, LWATokenResponse

logger = structlog.get_logger(__name__)


class SellerService:
    """Service for managing seller authentication and tokens."""

    def __init__(self, db: Session):
        self.db = db

    def create_or_update_seller(
        self,
        seller_id: str,
        marketplace_id: str,
        lwa_client_id: str,
        refresh_token: str,
        access_token: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        seller_name: Optional[str] = None,
        seller_email: Optional[str] = None,
    ) -> Seller:
        """
        Create or update seller with OAuth tokens.

        Args:
            seller_id: Amazon seller ID
            marketplace_id: Amazon marketplace ID
            lwa_client_id: LWA application client ID
            refresh_token: LWA refresh token (will be encrypted)
            access_token: Optional LWA access token (short-lived)
            expires_at: Optional access token expiration
            seller_name: Optional seller name
            seller_email: Optional seller email

        Returns:
            Seller object
        """
        logger.info("creating_or_updating_seller", seller_id=seller_id)

        # Encrypt refresh token
        encrypted_refresh = encrypt_refresh_token(refresh_token)

        # Check if seller exists
        seller = self.db.query(Seller).filter(Seller.id == seller_id).first()

        if seller:
            # Update existing seller
            seller.marketplace_id = marketplace_id
            seller.lwa_client_id = lwa_client_id
            seller.encrypted_refresh_token = encrypted_refresh
            seller.access_token_cached = access_token
            seller.access_token_expires_at = expires_at
            seller.status = SellerStatus.ACTIVE
            seller.last_token_refresh_at = datetime.utcnow()
            seller.last_token_refresh_error = None

            if seller_name:
                seller.seller_name = seller_name
            if seller_email:
                seller.seller_email = seller_email

            logger.info("seller_updated", seller_id=seller_id)
        else:
            # Create new seller
            seller = Seller(
                id=seller_id,
                marketplace_id=marketplace_id,
                lwa_client_id=lwa_client_id,
                encrypted_refresh_token=encrypted_refresh,
                access_token_cached=access_token,
                access_token_expires_at=expires_at,
                status=SellerStatus.ACTIVE,
                seller_name=seller_name,
                seller_email=seller_email,
                last_token_refresh_at=datetime.utcnow(),
            )
            self.db.add(seller)
            logger.info("seller_created", seller_id=seller_id)

        self.db.commit()
        self.db.refresh(seller)
        return seller

    def get_seller(self, seller_id: str) -> Optional[Seller]:
        """Get seller by ID."""
        return self.db.query(Seller).filter(Seller.id == seller_id).first()

    def get_decrypted_refresh_token(self, seller: Seller) -> str:
        """Get decrypted refresh token for seller."""
        return decrypt_refresh_token(seller.encrypted_refresh_token)

    async def get_valid_access_token(self, seller: Seller) -> str:
        """
        Get valid access token for seller, refreshing if necessary.

        Args:
            seller: Seller object

        Returns:
            Valid access token

        Raises:
            Exception: If token refresh fails
        """
        logger.info("getting_valid_access_token", seller_id=seller.id)

        # Check if cached token is valid
        if (
            seller.access_token_cached
            and seller.access_token_expires_at
            and datetime.utcnow() < seller.access_token_expires_at
        ):
            logger.info("using_cached_access_token", seller_id=seller.id)
            return seller.access_token_cached

        # Need to refresh token
        logger.info("refreshing_access_token", seller_id=seller.id)

        try:
            refresh_token = self.get_decrypted_refresh_token(seller)
            token_response = await lwa_client.refresh_access_token(refresh_token)

            # Update seller with new tokens
            seller.access_token_cached = token_response.access_token
            seller.access_token_expires_at = token_response.expires_at
            seller.last_token_refresh_at = datetime.utcnow()
            seller.last_token_refresh_error = None

            # If new refresh token provided, update it
            if token_response.refresh_token:
                logger.info("updating_refresh_token", seller_id=seller.id)
                seller.encrypted_refresh_token = encrypt_refresh_token(
                    token_response.refresh_token
                )

            self.db.commit()
            logger.info("access_token_refreshed", seller_id=seller.id)

            return token_response.access_token

        except Exception as e:
            error_msg = str(e)
            logger.error("token_refresh_failed", seller_id=seller.id, error=error_msg)

            # Update seller status
            seller.last_token_refresh_error = error_msg
            seller.last_token_refresh_at = datetime.utcnow()

            # Check if it's an authorization error
            if "invalid_grant" in error_msg.lower() or "unauthorized" in error_msg.lower():
                seller.status = SellerStatus.REAUTHORIZE_REQUIRED
                logger.warning("seller_reauthorization_required", seller_id=seller.id)

            self.db.commit()
            raise

    def mark_seller_status(self, seller_id: str, status: SellerStatus, error: Optional[str] = None):
        """Mark seller with specific status."""
        seller = self.get_seller(seller_id)
        if seller:
            seller.status = status
            if error:
                seller.last_token_refresh_error = error
            self.db.commit()
            logger.info("seller_status_updated", seller_id=seller_id, status=status)

    def revoke_seller(self, seller_id: str):
        """Revoke seller access."""
        seller = self.get_seller(seller_id)
        if seller:
            seller.status = SellerStatus.REVOKED
            seller.access_token_cached = None
            seller.access_token_expires_at = None
            # Keep encrypted refresh token for audit, but mark as revoked
            self.db.commit()
            logger.info("seller_revoked", seller_id=seller_id)
