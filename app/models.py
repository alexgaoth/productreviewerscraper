"""Database models for seller tokens and jobs."""

from datetime import datetime
from enum import Enum
from typing import Optional
from sqlalchemy import (
    Column, String, DateTime, Integer, Text, Boolean, Enum as SQLEnum, Float, JSON
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class SellerStatus(str, Enum):
    """Seller authorization status."""
    ACTIVE = "active"
    REAUTHORIZE_REQUIRED = "reauthorize_required"
    INSUFFICIENT_PERMISSIONS = "insufficient_permissions"
    REVOKED = "revoked"


class JobStatus(str, Enum):
    """Job execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Seller(Base):
    """Seller/Shop account with platform-specific tokens."""

    __tablename__ = "sellers"

    id = Column(String(100), primary_key=True)  # seller_id or shop_id
    platform = Column(String(20), nullable=False, default="amazon", index=True)  # amazon, shopify, etc.
    marketplace_id = Column(String(20), nullable=True, index=True)  # For Amazon; NULL for other platforms

    # OAuth credentials (platform-specific, stored as JSON)
    lwa_client_id = Column(String(200), nullable=True)  # For Amazon LWA
    encrypted_refresh_token = Column(Text, nullable=True)  # For Amazon; NULL for Shopify
    encrypted_access_token = Column(Text, nullable=True)  # For Shopify permanent token

    # Token metadata
    access_token_cached = Column(Text, nullable=True)  # Short-lived cache for Amazon
    access_token_expires_at = Column(DateTime, nullable=True)  # For Amazon; NULL for Shopify

    # Status
    status = Column(SQLEnum(SellerStatus), default=SellerStatus.ACTIVE, nullable=False, index=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    last_token_refresh_at = Column(DateTime, nullable=True)
    last_token_refresh_error = Column(Text, nullable=True)

    # Metadata
    seller_name = Column(String(200), nullable=True)
    seller_email = Column(String(200), nullable=True)

    def __repr__(self):
        return f"<Seller {self.id} platform={self.platform} status={self.status}>"


class FetchJob(Base):
    """Review fetch job tracking."""

    __tablename__ = "fetch_jobs"

    id = Column(String(100), primary_key=True)  # job_id
    platform = Column(String(20), nullable=False, default="amazon", index=True)  # amazon, shopify, etc.
    seller_id = Column(String(100), nullable=False, index=True)  # seller_id or shop_id
    marketplace_id = Column(String(20), nullable=True)  # For Amazon; NULL for other platforms

    # Request details (platform-agnostic JSON)
    asins = Column(JSON, nullable=True)  # For Amazon: List of ASINs; NULL for other platforms
    product_ids = Column(JSON, nullable=True)  # For Shopify: List of product IDs; NULL for Amazon
    request_params = Column(JSON, nullable=True)  # Additional platform-specific params
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    mode = Column(String(20), default="full")  # "full" or "recent"

    # Status
    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING, nullable=False, index=True)

    # Progress tracking (generic names for all platforms)
    total_items = Column(Integer, default=0)  # total_asins for Amazon, total products for Shopify
    completed_items = Column(Integer, default=0)
    failed_items = Column(Integer, default=0)
    total_reviews_fetched = Column(Integer, default=0)

    # Legacy fields for backward compatibility
    total_asins = Column(Integer, default=0)
    completed_asins = Column(Integer, default=0)
    failed_asins = Column(Integer, default=0)

    # Timing
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    # Results
    s3_raw_keys = Column(JSON, nullable=True)  # List of S3 keys for raw data
    s3_processed_keys = Column(JSON, nullable=True)  # List of S3 keys for processed data

    # Error tracking
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    # Metadata
    requested_by = Column(String(100), nullable=True)  # User/system that requested

    def __repr__(self):
        items = len(self.asins or []) if self.asins else len(self.product_ids or []) if self.product_ids else 0
        return f"<FetchJob {self.id} platform={self.platform} status={self.status} items={items}>"


class ASINFetchResult(Base):
    """Individual item (ASIN/Product) fetch results within a job."""

    __tablename__ = "asin_fetch_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(100), nullable=False, index=True)
    platform = Column(String(20), nullable=False, default="amazon", index=True)
    asin = Column(String(20), nullable=True, index=True)  # For Amazon
    product_id = Column(String(50), nullable=True, index=True)  # For Shopify

    # Status
    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING, nullable=False)

    # Results
    reviews_count = Column(Integer, default=0)
    pages_fetched = Column(Integer, default=0)

    # S3 locations
    raw_s3_key = Column(String(500), nullable=True)
    processed_s3_key = Column(String(500), nullable=True)

    # Pagination
    last_next_token = Column(String(500), nullable=True)  # For resuming

    # Timing
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Errors
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    def __repr__(self):
        item_id = self.asin if self.asin else self.product_id
        return f"<ItemFetchResult job={self.job_id} platform={self.platform} item={item_id} status={self.status}>"


class RateLimitBucket(Base):
    """Token bucket for rate limiting per seller."""

    __tablename__ = "rate_limit_buckets"

    seller_id = Column(String(100), primary_key=True)

    # Token bucket state
    tokens = Column(Float, nullable=False)  # Current tokens available
    max_tokens = Column(Float, nullable=False)  # Burst capacity
    refill_rate = Column(Float, nullable=False)  # Tokens per second
    last_refill_at = Column(DateTime, nullable=False)

    # Throttle state (from 429 responses)
    throttled_until = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<RateLimitBucket {self.seller_id} tokens={self.tokens:.2f}/{self.max_tokens}>"
