"""Celery tasks for fetching and processing reviews."""

import asyncio
import time
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session
import structlog

from app.worker.celery_app import celery_app
from app.database import get_db
from app.models import FetchJob, ASINFetchResult, JobStatus, SellerStatus
from app.auth.seller_service import SellerService
from app.spapi.client import (
    SPAPIClient,
    SPAPIAuthError,
    SPAPIRateLimitError,
    SPAPIServerError,
    SPAPIError,
)
from app.storage.s3_client import s3_storage
from app.storage.normalizer import normalizer
from app.worker.rate_limiter import RateLimiter
from app.config import settings

logger = structlog.get_logger(__name__)


def get_region_from_marketplace(marketplace_id: str) -> str:
    """
    Get region code from marketplace ID.

    Args:
        marketplace_id: Amazon marketplace ID

    Returns:
        Region code (na, eu, fe)
    """
    # NA marketplaces
    na_marketplaces = ["ATVPDKIKX0DER", "A2EUQ1WTGCTBG2", "A1AM78C64UM0Y8"]  # US, CA, MX
    # EU marketplaces
    eu_marketplaces = ["A1PA6795UKMFR9", "A1RKKUPIHCS9HS", "A13V1IB3VIYZZH"]  # DE, ES, FR, etc.
    # FE marketplaces
    fe_marketplaces = ["A1VC38T7YXB528", "A39IBJ37TRP1C6"]  # JP, AU

    if marketplace_id in na_marketplaces:
        return "na"
    elif marketplace_id in eu_marketplaces:
        return "eu"
    elif marketplace_id in fe_marketplaces:
        return "fe"
    else:
        return "na"  # Default to NA


async def retry_with_backoff(func, max_retries: int = 3, *args, **kwargs):
    """
    Retry function with exponential backoff.

    Args:
        func: Async function to retry
        max_retries: Maximum retry attempts
        *args: Function args
        **kwargs: Function kwargs

    Returns:
        Function result

    Raises:
        Exception: If all retries fail
    """
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except SPAPIServerError as e:
            if attempt >= max_retries - 1:
                raise

            backoff = min(
                settings.retry_backoff_base_seconds * (2 ** attempt),
                settings.retry_backoff_max_seconds,
            )
            # Add jitter
            backoff = backoff * (0.5 + 0.5 * (time.time() % 1))

            logger.warning(
                "retrying_after_server_error",
                attempt=attempt + 1,
                max_retries=max_retries,
                backoff=backoff,
                error=str(e),
            )
            await asyncio.sleep(backoff)
        except Exception:
            raise


async def fetch_asin_reviews_async(
    db: Session,
    job_id: str,
    seller_id: str,
    marketplace_id: str,
    asin: str,
) -> Dict[str, Any]:
    """
    Fetch all reviews for a single ASIN (async implementation).

    Args:
        db: Database session
        job_id: Job ID
        seller_id: Seller ID
        marketplace_id: Marketplace ID
        asin: Product ASIN

    Returns:
        Result dict with status and metadata
    """
    logger.info("fetching_asin_reviews", job_id=job_id, seller_id=seller_id, asin=asin)

    start_time = time.time()
    seller_service = SellerService(db)
    rate_limiter = RateLimiter(db, seller_id)

    # Get seller
    seller = seller_service.get_seller(seller_id)
    if not seller:
        raise ValueError(f"Seller {seller_id} not found")

    if seller.status != SellerStatus.ACTIVE:
        raise ValueError(f"Seller {seller_id} is not active: {seller.status}")

    # Create ASIN fetch result record
    asin_result = ASINFetchResult(
        job_id=job_id,
        asin=asin,
        status=JobStatus.IN_PROGRESS,
        started_at=datetime.utcnow(),
    )
    db.add(asin_result)
    db.commit()

    try:
        # Get valid access token
        access_token = await seller_service.get_valid_access_token(seller)

        # Create SP-API client
        region = get_region_from_marketplace(marketplace_id)
        spapi_client = SPAPIClient(region=region)

        # Fetch all pages
        all_reviews = []
        raw_s3_keys = []
        page_num = 0

        async for page_response in spapi_client.get_all_reviews(
            asin=asin,
            marketplace_id=marketplace_id,
            lwa_access_token=access_token,
        ):
            page_num += 1
            page_token = f"page{page_num}"

            # Rate limit
            await rate_limiter.acquire(tokens=1.0)

            # Check if page already exists (idempotency)
            if s3_storage.check_page_exists(seller_id, marketplace_id, asin, job_id, page_token):
                logger.info("page_already_exists_skipping", job_id=job_id, asin=asin, page=page_num)
                continue

            # Save raw response
            raw_s3_key = await s3_storage.save_raw_response(
                seller_id=seller_id,
                marketplace_id=marketplace_id,
                asin=asin,
                job_id=job_id,
                page_token=page_token,
                data=page_response.raw_data,
            )
            raw_s3_keys.append(raw_s3_key)

            # Normalize reviews
            for review in page_response.reviews:
                normalized = normalizer.normalize_review(review, asin, marketplace_id, page_token)
                all_reviews.append(normalized)

            logger.info(
                "page_processed",
                job_id=job_id,
                asin=asin,
                page=page_num,
                reviews_in_page=len(page_response.reviews),
                total_reviews=len(all_reviews),
            )

            # Update progress
            asin_result.pages_fetched = page_num
            asin_result.reviews_count = len(all_reviews)
            asin_result.last_next_token = page_response.next_token
            db.commit()

        # Create normalized artifact
        duration = time.time() - start_time
        normalized_artifact = normalizer.create_normalized_artifact(
            job_id=job_id,
            seller_id=seller_id,
            marketplace_id=marketplace_id,
            asin=asin,
            reviews=all_reviews,
            raw_s3_keys=raw_s3_keys,
            pages_fetched=page_num,
            next_token=None,
            fetch_duration_seconds=duration,
        )

        # Save normalized data
        processed_s3_key = await s3_storage.save_normalized_data(
            seller_id=seller_id,
            marketplace_id=marketplace_id,
            asin=asin,
            job_id=job_id,
            normalized_data=normalized_artifact,
            compress=True,
        )

        # Update ASIN result
        asin_result.status = JobStatus.SUCCESS
        asin_result.reviews_count = len(all_reviews)
        asin_result.pages_fetched = page_num
        asin_result.raw_s3_key = raw_s3_keys[0] if raw_s3_keys else None
        asin_result.processed_s3_key = processed_s3_key
        asin_result.completed_at = datetime.utcnow()
        db.commit()

        logger.info(
            "asin_fetch_completed",
            job_id=job_id,
            asin=asin,
            reviews_count=len(all_reviews),
            pages=page_num,
            duration=duration,
        )

        return {
            "status": "success",
            "asin": asin,
            "reviews_count": len(all_reviews),
            "pages_fetched": page_num,
            "raw_s3_keys": raw_s3_keys,
            "processed_s3_key": processed_s3_key,
        }

    except SPAPIAuthError as e:
        logger.error("spapi_auth_error", job_id=job_id, asin=asin, error=str(e))
        asin_result.status = JobStatus.FAILED
        asin_result.error_message = f"Authentication error: {str(e)}"
        asin_result.completed_at = datetime.utcnow()
        db.commit()

        # Mark seller for reauthorization
        seller_service.mark_seller_status(seller_id, SellerStatus.REAUTHORIZE_REQUIRED, str(e))

        raise

    except SPAPIRateLimitError as e:
        logger.warning("spapi_rate_limit", job_id=job_id, asin=asin, retry_after=e.retry_after)

        if e.retry_after:
            rate_limiter.set_throttled(e.retry_after)

        asin_result.status = JobStatus.FAILED
        asin_result.error_message = f"Rate limit exceeded: {str(e)}"
        asin_result.retry_count += 1
        db.commit()

        raise

    except Exception as e:
        logger.error("asin_fetch_failed", job_id=job_id, asin=asin, error=str(e), exc_info=True)
        asin_result.status = JobStatus.FAILED
        asin_result.error_message = str(e)
        asin_result.completed_at = datetime.utcnow()
        db.commit()

        raise


@celery_app.task(bind=True, name="fetch_asin_reviews")
def fetch_asin_reviews(self, job_id: str, seller_id: str, marketplace_id: str, asin: str):
    """
    Celery task to fetch reviews for a single ASIN.

    Args:
        job_id: Job ID
        seller_id: Seller ID
        marketplace_id: Marketplace ID
        asin: Product ASIN
    """
    with next(get_db()) as db:
        try:
            # Run async function
            result = asyncio.run(
                fetch_asin_reviews_async(db, job_id, seller_id, marketplace_id, asin)
            )
            return result
        except Exception as e:
            logger.error("task_failed", job_id=job_id, asin=asin, error=str(e))
            raise


@celery_app.task(bind=True, name="process_fetch_job")
def process_fetch_job(self, job_id: str):
    """
    Celery task to process a fetch job (spawn ASIN tasks).

    Args:
        job_id: Job ID
    """
    with next(get_db()) as db:
        logger.info("processing_fetch_job", job_id=job_id)

        # Get job
        job = db.query(FetchJob).filter(FetchJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        try:
            # Update job status
            job.status = JobStatus.IN_PROGRESS
            job.started_at = datetime.utcnow()
            job.total_asins = len(job.asins)
            db.commit()

            # Spawn ASIN fetch tasks
            for asin in job.asins:
                fetch_asin_reviews.delay(
                    job_id=job_id,
                    seller_id=job.seller_id,
                    marketplace_id=job.marketplace_id,
                    asin=asin,
                )

            logger.info(
                "fetch_job_tasks_spawned",
                job_id=job_id,
                asins_count=len(job.asins),
            )

            # Note: Job completion will be handled by a separate monitoring task
            # or webhook that checks when all ASIN tasks are done

        except Exception as e:
            logger.error("job_processing_failed", job_id=job_id, error=str(e))
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            db.commit()
            raise


@celery_app.task(name="check_job_completion")
def check_job_completion(job_id: str):
    """
    Check if all ASIN tasks for a job are completed.

    Args:
        job_id: Job ID
    """
    with next(get_db()) as db:
        job = db.query(FetchJob).filter(FetchJob.id == job_id).first()
        if not job:
            return

        # Get all ASIN results
        asin_results = db.query(ASINFetchResult).filter(
            ASINFetchResult.job_id == job_id
        ).all()

        total = len(asin_results)
        completed = sum(1 for r in asin_results if r.status in [JobStatus.SUCCESS, JobStatus.FAILED])
        successful = sum(1 for r in asin_results if r.status == JobStatus.SUCCESS)
        failed = sum(1 for r in asin_results if r.status == JobStatus.FAILED)

        job.completed_asins = successful
        job.failed_asins = failed
        job.total_reviews_fetched = sum(r.reviews_count or 0 for r in asin_results)

        # Check if all done
        if completed >= total:
            if failed == 0:
                job.status = JobStatus.SUCCESS
            elif successful > 0:
                job.status = JobStatus.PARTIAL_SUCCESS
            else:
                job.status = JobStatus.FAILED

            job.completed_at = datetime.utcnow()
            if job.started_at:
                duration = (job.completed_at - job.started_at).total_seconds()
                job.duration_seconds = duration

            # Collect S3 keys
            job.s3_raw_keys = [r.raw_s3_key for r in asin_results if r.raw_s3_key]
            job.s3_processed_keys = [r.processed_s3_key for r in asin_results if r.processed_s3_key]

            logger.info(
                "job_completed",
                job_id=job_id,
                status=job.status,
                successful=successful,
                failed=failed,
            )

        db.commit()
