"""Celery application configuration."""

from celery import Celery
from app.config import settings

# Create Celery app
celery_app = Celery(
    "amazon_reviews_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.job_timeout_seconds,
    task_soft_time_limit=settings.job_timeout_seconds - 60,
    worker_prefetch_multiplier=1,  # Fetch one task at a time
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["app.worker"])
