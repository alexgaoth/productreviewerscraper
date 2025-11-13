"""Prometheus metrics for monitoring."""

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry

# Create registry
registry = CollectorRegistry()

# Reviews fetched
reviews_fetched_total = Counter(
    "reviews_fetched_total",
    "Total number of reviews fetched",
    ["seller_id", "marketplace_id"],
    registry=registry,
)

# Jobs
jobs_started_total = Counter(
    "jobs_started_total",
    "Total number of jobs started",
    ["seller_id"],
    registry=registry,
)

jobs_completed_total = Counter(
    "jobs_completed_total",
    "Total number of jobs completed",
    ["seller_id", "status"],
    registry=registry,
)

jobs_failed_total = Counter(
    "jobs_failed_total",
    "Total number of jobs failed",
    ["seller_id", "error_type"],
    registry=registry,
)

# LWA token operations
lwa_token_refresh_total = Counter(
    "lwa_token_refresh_total",
    "Total number of LWA token refreshes",
    ["seller_id", "status"],
    registry=registry,
)

lwa_refresh_failures_total = Counter(
    "lwa_refresh_failures_total",
    "Total number of LWA refresh failures",
    ["seller_id", "error_type"],
    registry=registry,
)

# SP-API operations
spapi_requests_total = Counter(
    "spapi_requests_total",
    "Total number of SP-API requests",
    ["endpoint", "status_code"],
    registry=registry,
)

spapi_errors_total = Counter(
    "spapi_errors_total",
    "Total number of SP-API errors",
    ["error_type"],
    registry=registry,
)

spapi_rate_limits_total = Counter(
    "spapi_rate_limits_total",
    "Total number of rate limit hits",
    ["seller_id"],
    registry=registry,
)

# S3 operations
s3_put_duration_seconds = Histogram(
    "s3_put_duration_seconds",
    "S3 PUT operation duration",
    ["bucket", "operation_type"],
    registry=registry,
)

s3_put_errors_total = Counter(
    "s3_put_errors_total",
    "Total number of S3 PUT errors",
    ["bucket", "error_type"],
    registry=registry,
)

# Active jobs
active_jobs = Gauge(
    "active_jobs",
    "Number of currently active jobs",
    registry=registry,
)

# Seller status
sellers_by_status = Gauge(
    "sellers_by_status",
    "Number of sellers by status",
    ["status"],
    registry=registry,
)
