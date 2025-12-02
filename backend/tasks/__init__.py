"""Celery tasks module."""

from tasks.celery_app import celery_app
from tasks.indexing import (
    clone_and_index_code,
    fetch_and_index_issues,
    fetch_and_index_merge_requests,
    index_project,
)
from tasks.sync import refresh_projects

__all__ = [
    "celery_app",
    "index_project",
    "fetch_and_index_issues",
    "fetch_and_index_merge_requests",
    "clone_and_index_code",
    "refresh_projects",
]
