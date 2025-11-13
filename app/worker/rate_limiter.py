"""Rate limiting for SP-API requests."""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
import structlog

from app.config import settings
from app.models import RateLimitBucket

logger = structlog.get_logger(__name__)


class RateLimiter:
    """Token bucket rate limiter for API requests."""

    def __init__(
        self,
        db: Session,
        seller_id: str,
        rate: Optional[float] = None,
        burst: Optional[int] = None,
    ):
        """
        Initialize rate limiter.

        Args:
            db: Database session
            seller_id: Seller ID
            rate: Refill rate (tokens per second)
            burst: Maximum tokens (burst capacity)
        """
        self.db = db
        self.seller_id = seller_id
        self.rate = rate or settings.spapi_requests_per_second
        self.burst = burst or settings.spapi_burst_capacity

    def _get_or_create_bucket(self) -> RateLimitBucket:
        """Get or create rate limit bucket for seller."""
        bucket = self.db.query(RateLimitBucket).filter(
            RateLimitBucket.seller_id == self.seller_id
        ).first()

        if not bucket:
            bucket = RateLimitBucket(
                seller_id=self.seller_id,
                tokens=float(self.burst),
                max_tokens=float(self.burst),
                refill_rate=self.rate,
                last_refill_at=datetime.utcnow(),
            )
            self.db.add(bucket)
            self.db.commit()
            self.db.refresh(bucket)

        return bucket

    def _refill_tokens(self, bucket: RateLimitBucket):
        """Refill tokens based on elapsed time."""
        now = datetime.utcnow()
        elapsed = (now - bucket.last_refill_at).total_seconds()

        if elapsed > 0:
            # Add tokens based on elapsed time
            new_tokens = elapsed * bucket.refill_rate
            bucket.tokens = min(bucket.tokens + new_tokens, bucket.max_tokens)
            bucket.last_refill_at = now

            logger.debug(
                "tokens_refilled",
                seller_id=self.seller_id,
                tokens=bucket.tokens,
                elapsed=elapsed,
            )

    async def acquire(self, tokens: float = 1.0) -> bool:
        """
        Acquire tokens for making a request.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if tokens acquired, False otherwise
        """
        bucket = self._get_or_create_bucket()

        # Check if throttled
        if bucket.throttled_until and datetime.utcnow() < bucket.throttled_until:
            wait_seconds = (bucket.throttled_until - datetime.utcnow()).total_seconds()
            logger.warning(
                "rate_limiter_throttled",
                seller_id=self.seller_id,
                wait_seconds=wait_seconds,
            )
            await asyncio.sleep(wait_seconds)
            bucket.throttled_until = None

        # Refill tokens
        self._refill_tokens(bucket)

        # Check if enough tokens
        if bucket.tokens >= tokens:
            bucket.tokens -= tokens
            self.db.commit()
            logger.debug("tokens_acquired", seller_id=self.seller_id, remaining=bucket.tokens)
            return True
        else:
            # Need to wait for tokens
            wait_time = (tokens - bucket.tokens) / bucket.refill_rate
            logger.info(
                "rate_limit_waiting",
                seller_id=self.seller_id,
                wait_seconds=wait_time,
            )
            await asyncio.sleep(wait_time)

            # Try again after waiting
            self._refill_tokens(bucket)
            if bucket.tokens >= tokens:
                bucket.tokens -= tokens
                self.db.commit()
                return True

            return False

    def set_throttled(self, retry_after_seconds: int):
        """
        Set throttled state from 429 response.

        Args:
            retry_after_seconds: Seconds to wait before retry
        """
        bucket = self._get_or_create_bucket()
        bucket.throttled_until = datetime.utcnow() + timedelta(seconds=retry_after_seconds)
        self.db.commit()

        logger.warning(
            "rate_limiter_throttled_by_api",
            seller_id=self.seller_id,
            retry_after=retry_after_seconds,
        )
