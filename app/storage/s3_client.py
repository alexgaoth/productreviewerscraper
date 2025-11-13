"""S3 client for storing raw and normalized review data."""

import json
import gzip
from datetime import datetime
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


class S3StorageClient:
    """Client for storing review data in S3."""

    def __init__(
        self,
        raw_bucket: Optional[str] = None,
        processed_bucket: Optional[str] = None,
    ):
        """
        Initialize S3 client.

        Args:
            raw_bucket: S3 bucket for raw data
            processed_bucket: S3 bucket for processed data
        """
        self.raw_bucket = raw_bucket or settings.s3_bucket_raw
        self.processed_bucket = processed_bucket or settings.s3_bucket_processed

        # Initialize boto3 S3 client
        self.s3_client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )

    def _generate_raw_key(
        self,
        seller_id: str,
        job_id: str,
        page_token: str = "page1",
        platform: str = "amazon",
        marketplace_id: Optional[str] = None,
        asin: Optional[str] = None,
        product_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> str:
        """
        Generate S3 key for raw data with platform support.

        Format: raw/{platform}/{seller_id}/{item_id}/{YYYY}/{MM}/{DD}/{job_id}/{page_token}.json

        Args:
            seller_id: Seller/Shop ID
            job_id: Job ID
            page_token: Page identifier
            platform: Platform name (amazon, shopify, etc.)
            marketplace_id: Marketplace ID (Amazon only, for legacy compat)
            asin: Product ASIN (Amazon)
            product_id: Product ID (Shopify)
            timestamp: Optional timestamp (defaults to now)

        Returns:
            S3 key
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        # Determine item identifier based on platform
        if platform == "amazon":
            item_id = f"{marketplace_id}/{asin}" if marketplace_id and asin else asin or "unknown"
        elif platform == "shopify":
            item_id = product_id or "all"
        else:
            item_id = asin or product_id or "unknown"

        return (
            f"raw/{platform}/{seller_id}/{item_id}/"
            f"{timestamp.year:04d}/{timestamp.month:02d}/{timestamp.day:02d}/"
            f"{job_id}/{page_token}.json"
        )

    def _generate_processed_key(
        self,
        seller_id: str,
        job_id: str,
        platform: str = "amazon",
        marketplace_id: Optional[str] = None,
        asin: Optional[str] = None,
        product_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> str:
        """
        Generate S3 key for processed data with platform support.

        Format: processed/{platform}/{seller_id}/{item_id}/{YYYY}/{MM}/{DD}/{job_id}.json

        Args:
            seller_id: Seller/Shop ID
            job_id: Job ID
            platform: Platform name (amazon, shopify, etc.)
            marketplace_id: Marketplace ID (Amazon only, for legacy compat)
            asin: Product ASIN (Amazon)
            product_id: Product ID (Shopify)
            timestamp: Optional timestamp (defaults to now)

        Returns:
            S3 key
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        # Determine item identifier based on platform
        if platform == "amazon":
            item_id = f"{marketplace_id}/{asin}" if marketplace_id and asin else asin or "unknown"
        elif platform == "shopify":
            item_id = product_id or "all"
        else:
            item_id = asin or product_id or "unknown"

        return (
            f"processed/{platform}/{seller_id}/{item_id}/"
            f"{timestamp.year:04d}/{timestamp.month:02d}/{timestamp.day:02d}/"
            f"{job_id}.json"
        )

    async def save_raw_response(
        self,
        seller_id: str,
        job_id: str,
        page_token: str,
        data: Dict[str, Any],
        platform: str = "amazon",
        marketplace_id: Optional[str] = None,
        asin: Optional[str] = None,
        product_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Save raw API response to S3 with platform support.

        Args:
            seller_id: Seller/Shop ID
            job_id: Job ID
            page_token: Page identifier
            data: Raw API response data
            platform: Platform name (amazon, shopify, etc.)
            marketplace_id: Marketplace ID (Amazon)
            asin: Product ASIN (Amazon)
            product_id: Product ID (Shopify)
            metadata: Optional S3 object metadata

        Returns:
            S3 key where data was saved

        Raises:
            Exception: If S3 upload fails
        """
        key = self._generate_raw_key(
            seller_id=seller_id,
            job_id=job_id,
            page_token=page_token,
            platform=platform,
            marketplace_id=marketplace_id,
            asin=asin,
            product_id=product_id,
        )

        # Convert to JSON
        json_data = json.dumps(data, indent=2)

        # Prepare metadata
        s3_metadata = {
            "platform": platform,
            "seller_id": seller_id,
            "job_id": job_id,
            "page_token": page_token,
            "fetched_at": datetime.utcnow().isoformat(),
        }
        if marketplace_id:
            s3_metadata["marketplace_id"] = marketplace_id
        if asin:
            s3_metadata["asin"] = asin
        if product_id:
            s3_metadata["product_id"] = product_id
        if metadata:
            s3_metadata.update(metadata)

        logger.info("saving_raw_response_to_s3", bucket=self.raw_bucket, key=key)

        try:
            self.s3_client.put_object(
                Bucket=self.raw_bucket,
                Key=key,
                Body=json_data.encode("utf-8"),
                ContentType="application/json",
                Metadata=s3_metadata,
            )

            logger.info("raw_response_saved", bucket=self.raw_bucket, key=key)
            return f"s3://{self.raw_bucket}/{key}"

        except ClientError as e:
            logger.error("s3_upload_failed", bucket=self.raw_bucket, key=key, error=str(e))
            raise

    async def save_normalized_data(
        self,
        seller_id: str,
        job_id: str,
        normalized_data: Dict[str, Any],
        platform: str = "amazon",
        marketplace_id: Optional[str] = None,
        asin: Optional[str] = None,
        product_id: Optional[str] = None,
        compress: bool = False,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Save normalized review data to S3 with platform support.

        Args:
            seller_id: Seller/Shop ID
            job_id: Job ID
            normalized_data: Normalized review data
            platform: Platform name (amazon, shopify, etc.)
            marketplace_id: Marketplace ID (Amazon)
            asin: Product ASIN (Amazon)
            product_id: Product ID (Shopify)
            compress: Whether to gzip compress
            metadata: Optional S3 object metadata

        Returns:
            S3 key where data was saved

        Raises:
            Exception: If S3 upload fails
        """
        key = self._generate_processed_key(
            seller_id=seller_id,
            job_id=job_id,
            platform=platform,
            marketplace_id=marketplace_id,
            asin=asin,
            product_id=product_id,
        )

        if compress:
            key += ".gz"

        # Convert to JSON
        json_data = json.dumps(normalized_data, indent=2)

        # Prepare body
        if compress:
            body = gzip.compress(json_data.encode("utf-8"))
            content_type = "application/json"
            content_encoding = "gzip"
        else:
            body = json_data.encode("utf-8")
            content_type = "application/json"
            content_encoding = None

        # Prepare metadata
        s3_metadata = {
            "platform": platform,
            "seller_id": seller_id,
            "job_id": job_id,
            "reviews_count": str(normalized_data.get("reviews_count", 0)),
            "processed_at": datetime.utcnow().isoformat(),
        }
        if marketplace_id:
            s3_metadata["marketplace_id"] = marketplace_id
        if asin:
            s3_metadata["asin"] = asin
        if product_id:
            s3_metadata["product_id"] = product_id
        if metadata:
            s3_metadata.update(metadata)

        logger.info("saving_normalized_data_to_s3", bucket=self.processed_bucket, key=key, compressed=compress)

        try:
            put_args = {
                "Bucket": self.processed_bucket,
                "Key": key,
                "Body": body,
                "ContentType": content_type,
                "Metadata": s3_metadata,
            }
            if content_encoding:
                put_args["ContentEncoding"] = content_encoding

            self.s3_client.put_object(**put_args)

            logger.info("normalized_data_saved", bucket=self.processed_bucket, key=key)
            return f"s3://{self.processed_bucket}/{key}"

        except ClientError as e:
            logger.error("s3_upload_failed", bucket=self.processed_bucket, key=key, error=str(e))
            raise

    def check_page_exists(
        self,
        seller_id: str,
        job_id: str,
        page_token: str,
        platform: str = "amazon",
        marketplace_id: Optional[str] = None,
        asin: Optional[str] = None,
        product_id: Optional[str] = None,
    ) -> bool:
        """
        Check if a raw page already exists in S3 (for idempotency).

        Args:
            seller_id: Seller/Shop ID
            job_id: Job ID
            page_token: Page identifier
            platform: Platform name (amazon, shopify, etc.)
            marketplace_id: Marketplace ID (Amazon)
            asin: Product ASIN (Amazon)
            product_id: Product ID (Shopify)

        Returns:
            True if page exists, False otherwise
        """
        key = self._generate_raw_key(
            seller_id=seller_id,
            job_id=job_id,
            page_token=page_token,
            platform=platform,
            marketplace_id=marketplace_id,
            asin=asin,
            product_id=product_id,
        )

        try:
            self.s3_client.head_object(Bucket=self.raw_bucket, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise


# Global S3 storage client
s3_storage = S3StorageClient()
