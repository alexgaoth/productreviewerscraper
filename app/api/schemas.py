"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# Auth schemas
class OAuthCallbackRequest(BaseModel):
    """Request body for OAuth callback."""
    code: str
    state: str
    seller_id: str
    marketplace_id: str = "ATVPDKIKX0DER"  # Default to US
    seller_name: Optional[str] = None
    seller_email: Optional[str] = None


class OAuthCallbackResponse(BaseModel):
    """Response for OAuth callback."""
    ok: bool
    seller_id: str
    message: str


class TokenMetadataResponse(BaseModel):
    """Seller token metadata (not including actual tokens)."""
    seller_id: str
    marketplace_id: str
    status: str
    created_at: datetime
    last_token_refresh_at: Optional[datetime]
    last_token_refresh_error: Optional[str]


# Fetch job schemas
class FetchReviewsRequest(BaseModel):
    """Request to fetch reviews."""
    seller_id: str
    marketplace_id: str = "ATVPDKIKX0DER"
    asins: List[str] = Field(..., min_items=1, max_items=100)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    mode: str = Field(default="full", pattern="^(full|recent)$")


class FetchReviewsResponse(BaseModel):
    """Response for fetch reviews request."""
    job_id: str
    status: str
    message: str
    asins_count: int


class JobStatusResponse(BaseModel):
    """Job status response."""
    job_id: str
    status: str
    seller_id: str
    marketplace_id: str
    asins: List[str]
    total_asins: int
    completed_asins: int
    failed_asins: int
    total_reviews_fetched: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    error_message: Optional[str]
    s3_raw_keys: Optional[List[str]]
    s3_processed_keys: Optional[List[str]]


class ASINResultResponse(BaseModel):
    """ASIN fetch result."""
    asin: str
    status: str
    reviews_count: int
    pages_fetched: int
    error_message: Optional[str]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: datetime
    version: str
