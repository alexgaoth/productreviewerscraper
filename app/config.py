"""Application configuration management."""

import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application
    app_name: str = Field(default="amazon-seller-reviews-service", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Server
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    # Database
    database_url: str = Field(default="sqlite:///./seller_reviews.db", alias="DATABASE_URL")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # AWS Configuration
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    aws_access_key_id: Optional[str] = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")

    # AWS Secrets Manager
    secrets_manager_enabled: bool = Field(default=False, alias="SECRETS_MANAGER_ENABLED")
    lwa_secrets_arn: Optional[str] = Field(default=None, alias="LWA_SECRETS_ARN")
    spapi_secrets_arn: Optional[str] = Field(default=None, alias="SPAPI_SECRETS_ARN")

    # S3 Storage
    s3_bucket_raw: str = Field(default="amazon-reviews-raw-dev", alias="S3_BUCKET_RAW")
    s3_bucket_processed: str = Field(default="amazon-reviews-processed-dev", alias="S3_BUCKET_PROCESSED")

    # Login with Amazon (LWA)
    lwa_client_id: str = Field(alias="LWA_CLIENT_ID")
    lwa_client_secret: str = Field(alias="LWA_CLIENT_SECRET")
    lwa_redirect_uri: str = Field(alias="LWA_REDIRECT_URI")
    lwa_token_url: str = "https://api.amazon.com/auth/o2/token"
    lwa_authorization_url: str = "https://www.amazon.com/ap/oa"

    # SP-API Configuration
    spapi_aws_access_key_id: str = Field(alias="SPAPI_AWS_ACCESS_KEY_ID")
    spapi_aws_secret_access_key: str = Field(alias="SPAPI_AWS_SECRET_ACCESS_KEY")
    spapi_role_arn: Optional[str] = Field(default=None, alias="SPAPI_ROLE_ARN")
    spapi_endpoint_na: str = Field(
        default="https://sellingpartnerapi-na.amazon.com",
        alias="SPAPI_ENDPOINT_NA"
    )
    spapi_endpoint_eu: str = Field(
        default="https://sellingpartnerapi-eu.amazon.com",
        alias="SPAPI_ENDPOINT_EU"
    )
    spapi_endpoint_fe: str = Field(
        default="https://sellingpartnerapi-fe.amazon.com",
        alias="SPAPI_ENDPOINT_FE"
    )

    # Encryption (for refresh tokens)
    encryption_key: str = Field(alias="ENCRYPTION_KEY")

    # Rate Limiting
    max_concurrent_jobs_per_seller: int = Field(default=3, alias="MAX_CONCURRENT_JOBS_PER_SELLER")
    spapi_requests_per_second: float = Field(default=2.0, alias="SPAPI_REQUESTS_PER_SECOND")
    spapi_burst_capacity: int = Field(default=10, alias="SPAPI_BURST_CAPACITY")

    # Job Configuration
    job_timeout_seconds: int = Field(default=3600, alias="JOB_TIMEOUT_SECONDS")
    max_retries: int = Field(default=3, alias="MAX_RETRIES")
    retry_backoff_base_seconds: int = Field(default=2, alias="RETRY_BACKOFF_BASE_SECONDS")
    retry_backoff_max_seconds: int = Field(default=64, alias="RETRY_BACKOFF_MAX_SECONDS")

    # Celery
    celery_broker_url: str = Field(default="redis://localhost:6379/0", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/0", alias="CELERY_RESULT_BACKEND")

    # Monitoring
    metrics_enabled: bool = Field(default=True, alias="METRICS_ENABLED")
    metrics_port: int = Field(default=9090, alias="METRICS_PORT")

    def get_spapi_endpoint(self, region: str = "na") -> str:
        """Get SP-API endpoint URL for region."""
        region_map = {
            "na": self.spapi_endpoint_na,
            "eu": self.spapi_endpoint_eu,
            "fe": self.spapi_endpoint_fe,
        }
        return region_map.get(region.lower(), self.spapi_endpoint_na)


# Global settings instance
settings = Settings()
