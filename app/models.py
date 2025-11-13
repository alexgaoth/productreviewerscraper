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
    """Seller account with LWA tokens."""

    __tablename__ = "sellers"

    id = Column(String(100), primary_key=True)  # seller_id from Amazon
    marketplace_id = Column(String(20), nullable=False, index=True)

    # LWA OAuth
    lwa_client_id = Column(String(200), nullable=False)  # Which LWA app
    encrypted_refresh_token = Column(Text, nullable=False)  # Encrypted refresh token

    # Token metadata
    access_token_cached = Column(Text, nullable=True)  # Short-lived, not persisted long-term
    access_token_expires_at = Column(DateTime, nullable=True)

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
        return f"<Seller {self.id} status={self.status}>"


class FetchJob(Base):
    """Review fetch job tracking."""

    __tablename__ = "fetch_jobs"

    id = Column(String(100), primary_key=True)  # job_id
    seller_id = Column(String(100), nullable=False, index=True)
    marketplace_id = Column(String(20), nullable=False)

    # Request details
    asins = Column(JSON, nullable=False)  # List of ASINs
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    mode = Column(String(20), default="full")  # "full" or "recent"

    # Status
    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING, nullable=False, index=True)

    # Progress tracking
    total_asins = Column(Integer, default=0)
    completed_asins = Column(Integer, default=0)
    failed_asins = Column(Integer, default=0)
    total_reviews_fetched = Column(Integer, default=0)

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
        return f"<FetchJob {self.id} status={self.status} asins={len(self.asins)}>"


class ASINFetchResult(Base):
    """Individual ASIN fetch results within a job."""

    __tablename__ = "asin_fetch_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(100), nullable=False, index=True)
    asin = Column(String(20), nullable=False, index=True)

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
        return f"<ASINFetchResult job={self.job_id} asin={self.asin} status={self.status}>"


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
