"""API routes for the service."""

import uuid
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import structlog

from app.api.schemas import (
    OAuthCallbackRequest,
    OAuthCallbackResponse,
    TokenMetadataResponse,
    FetchReviewsRequest,
    FetchReviewsResponse,
    JobStatusResponse,
    ASINResultResponse,
    HealthResponse,
)
from app.database import get_db_session
from app.auth.lwa_client import lwa_client
from app.auth.seller_service import SellerService
from app.models import FetchJob, ASINFetchResult, JobStatus
from app.worker.tasks import process_fetch_job, check_job_completion
from app import __version__

logger = structlog.get_logger(__name__)

router = APIRouter()


# Health check
@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version=__version__,
    )


# OAuth / Authentication routes
@router.get("/auth/amazon/start")
async def start_oauth_flow(
    seller_id: str = Query(..., description="Seller identifier"),
    return_to: str = Query(None, description="Return URL after auth"),
):
    """
    Start OAuth flow by redirecting to Amazon LWA authorization page.

    Args:
        seller_id: Seller identifier (for state tracking)
        return_to: Optional return URL

    Returns:
        Redirect to Amazon authorization page
    """
    logger.info("starting_oauth_flow", seller_id=seller_id)

    # Generate authorization URL with state
    state_data = f"{seller_id}:{return_to or ''}"
    auth_url, state = lwa_client.get_authorization_url(state=state_data)

    logger.info("redirecting_to_amazon", seller_id=seller_id)

    return RedirectResponse(url=auth_url)


@router.post("/auth/amazon/callback", response_model=OAuthCallbackResponse)
async def oauth_callback(
    request: OAuthCallbackRequest,
    db: Session = Depends(get_db_session),
):
    """
    Handle OAuth callback after user authorizes.

    Args:
        request: Callback request with code and state
        db: Database session

    Returns:
        Success response
    """
    logger.info("handling_oauth_callback", seller_id=request.seller_id)

    try:
        # Exchange code for tokens
        token_response = await lwa_client.exchange_code_for_tokens(request.code)

        # Store seller with tokens
        seller_service = SellerService(db)
        seller = seller_service.create_or_update_seller(
            seller_id=request.seller_id,
            marketplace_id=request.marketplace_id,
            lwa_client_id=lwa_client.client_id,
            refresh_token=token_response.refresh_token,
            access_token=token_response.access_token,
            expires_at=token_response.expires_at,
            seller_name=request.seller_name,
            seller_email=request.seller_email,
        )

        logger.info("seller_authorized", seller_id=seller.id)

        return OAuthCallbackResponse(
            ok=True,
            seller_id=seller.id,
            message="Authorization successful",
        )

    except Exception as e:
        logger.error("oauth_callback_failed", seller_id=request.seller_id, error=str(e))
        raise HTTPException(status_code=400, detail=f"Authorization failed: {str(e)}")


@router.post("/seller/{seller_id}/refresh-token")
async def refresh_seller_token(
    seller_id: str,
    db: Session = Depends(get_db_session),
):
    """
    Manually trigger token refresh for a seller.

    Args:
        seller_id: Seller ID
        db: Database session

    Returns:
        Success response
    """
    logger.info("manual_token_refresh", seller_id=seller_id)

    seller_service = SellerService(db)
    seller = seller_service.get_seller(seller_id)

    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")

    try:
        await seller_service.get_valid_access_token(seller)
        return {"ok": True, "message": "Token refreshed successfully"}

    except Exception as e:
        logger.error("token_refresh_failed", seller_id=seller_id, error=str(e))
        raise HTTPException(status_code=400, detail=f"Token refresh failed: {str(e)}")


@router.get("/seller/{seller_id}/tokens", response_model=TokenMetadataResponse)
async def get_seller_tokens_metadata(
    seller_id: str,
    db: Session = Depends(get_db_session),
):
    """
    Get seller token metadata (not actual tokens).

    Args:
        seller_id: Seller ID
        db: Database session

    Returns:
        Token metadata
    """
    seller_service = SellerService(db)
    seller = seller_service.get_seller(seller_id)

    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")

    return TokenMetadataResponse(
        seller_id=seller.id,
        marketplace_id=seller.marketplace_id,
        status=seller.status.value,
        created_at=seller.created_at,
        last_token_refresh_at=seller.last_token_refresh_at,
        last_token_refresh_error=seller.last_token_refresh_error,
    )


# Fetch job routes
@router.post("/fetch/reviews", response_model=FetchReviewsResponse)
async def fetch_reviews(
    request: FetchReviewsRequest,
    db: Session = Depends(get_db_session),
):
    """
    Request to fetch reviews for ASINs.

    Args:
        request: Fetch request
        db: Database session

    Returns:
        Job information
    """
    logger.info(
        "fetch_reviews_requested",
        seller_id=request.seller_id,
        asins_count=len(request.asins),
    )

    # Validate seller exists
    seller_service = SellerService(db)
    seller = seller_service.get_seller(request.seller_id)

    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")

    if seller.status.value != "active":
        raise HTTPException(
            status_code=400,
            detail=f"Seller is not active. Status: {seller.status.value}",
        )

    # Create job
    job_id = f"job-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"

    job = FetchJob(
        id=job_id,
        seller_id=request.seller_id,
        marketplace_id=request.marketplace_id,
        asins=request.asins,
        start_date=request.start_date,
        end_date=request.end_date,
        mode=request.mode,
        total_asins=len(request.asins),
        status=JobStatus.PENDING,
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    logger.info("fetch_job_created", job_id=job_id, asins_count=len(request.asins))

    # Enqueue job processing
    process_fetch_job.delay(job_id)

    return FetchReviewsResponse(
        job_id=job_id,
        status=JobStatus.PENDING.value,
        message="Job queued successfully",
        asins_count=len(request.asins),
    )


@router.get("/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    db: Session = Depends(get_db_session),
):
    """
    Get job status.

    Args:
        job_id: Job ID
        db: Database session

    Returns:
        Job status
    """
    job = db.query(FetchJob).filter(FetchJob.id == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Trigger completion check if job is in progress
    if job.status == JobStatus.IN_PROGRESS:
        check_job_completion.delay(job_id)

    return JobStatusResponse(
        job_id=job.id,
        status=job.status.value,
        seller_id=job.seller_id,
        marketplace_id=job.marketplace_id,
        asins=job.asins,
        total_asins=job.total_asins,
        completed_asins=job.completed_asins,
        failed_asins=job.failed_asins,
        total_reviews_fetched=job.total_reviews_fetched,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration_seconds=job.duration_seconds,
        error_message=job.error_message,
        s3_raw_keys=job.s3_raw_keys,
        s3_processed_keys=job.s3_processed_keys,
    )


@router.get("/jobs/{job_id}/asins", response_model=List[ASINResultResponse])
async def get_job_asin_results(
    job_id: str,
    db: Session = Depends(get_db_session),
):
    """
    Get detailed ASIN results for a job.

    Args:
        job_id: Job ID
        db: Database session

    Returns:
        List of ASIN results
    """
    results = db.query(ASINFetchResult).filter(
        ASINFetchResult.job_id == job_id
    ).all()

    return [
        ASINResultResponse(
            asin=r.asin,
            status=r.status.value,
            reviews_count=r.reviews_count,
            pages_fetched=r.pages_fetched,
            error_message=r.error_message,
        )
        for r in results
    ]


@router.get("/seller/{seller_id}/jobs", response_model=List[JobStatusResponse])
async def get_seller_jobs(
    seller_id: str,
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db_session),
):
    """
    Get recent jobs for a seller.

    Args:
        seller_id: Seller ID
        limit: Maximum number of jobs to return
        db: Database session

    Returns:
        List of jobs
    """
    jobs = (
        db.query(FetchJob)
        .filter(FetchJob.seller_id == seller_id)
        .order_by(FetchJob.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        JobStatusResponse(
            job_id=job.id,
            status=job.status.value,
            seller_id=job.seller_id,
            marketplace_id=job.marketplace_id,
            asins=job.asins,
            total_asins=job.total_asins,
            completed_asins=job.completed_asins,
            failed_asins=job.failed_asins,
            total_reviews_fetched=job.total_reviews_fetched,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            duration_seconds=job.duration_seconds,
            error_message=job.error_message,
            s3_raw_keys=job.s3_raw_keys,
            s3_processed_keys=job.s3_processed_keys,
        )
        for job in jobs
    ]
