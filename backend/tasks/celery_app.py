"""Celery application configuration."""

from celery import Celery

from config import get_settings

settings = get_settings()

celery_app = Celery(
    "gitlab_chat",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["tasks.indexing", "tasks.sync"],
)

# Celery configuration
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Task routing
    task_routes={
        "tasks.indexing.*": {"queue": "indexing"},
        "tasks.sync.*": {"queue": "gitlab_sync"},
    },
    # Task settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Result settings
    result_expires=3600,  # 1 hour
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_concurrency=4,
)
