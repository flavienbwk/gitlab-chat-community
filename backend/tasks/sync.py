"""GitLab synchronization tasks."""

import asyncio
from typing import Dict, List

from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from config import get_settings
from core.gitlab_client import GitLabClient
from db.models import Project

logger = get_task_logger(__name__)
settings = get_settings()


def get_sync_session() -> Session:
    """Get a synchronous database session for Celery tasks."""
    engine = create_engine(settings.sync_database_url)
    return Session(engine)


def run_async(coro):
    """Run async coroutine in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def refresh_projects(self) -> Dict:
    """Refresh project list from GitLab.

    Fetches all accessible projects and upserts them into the database.
    """
    logger.info("Starting project refresh from GitLab")

    try:
        gitlab = GitLabClient()

        # Fetch all accessible projects
        projects = run_async(gitlab.get_projects(membership=True))

        logger.info(f"Found {len(projects)} projects from GitLab")

        created = 0
        updated = 0

        with get_sync_session() as session:
            for proj in projects:
                existing = (
                    session.query(Project)
                    .filter(Project.gitlab_id == proj["id"])
                    .first()
                )

                if existing:
                    # Update existing project
                    existing.name = proj["name"]
                    existing.path_with_namespace = proj["path_with_namespace"]
                    existing.description = proj.get("description")
                    existing.default_branch = proj.get("default_branch", "main")
                    existing.http_url_to_repo = proj.get("http_url_to_repo")
                    updated += 1
                else:
                    # Create new project
                    new_project = Project(
                        gitlab_id=proj["id"],
                        name=proj["name"],
                        path_with_namespace=proj["path_with_namespace"],
                        description=proj.get("description"),
                        default_branch=proj.get("default_branch", "main"),
                        http_url_to_repo=proj.get("http_url_to_repo"),
                    )
                    session.add(new_project)
                    created += 1

            session.commit()

        logger.info(f"Project refresh complete: {created} created, {updated} updated")

        return {
            "status": "completed",
            "total_projects": len(projects),
            "created": created,
            "updated": updated,
        }

    except Exception as exc:
        logger.error(f"Failed to refresh projects: {exc}")
        raise self.retry(exc=exc)


@shared_task
def sync_project_updates(project_id: int) -> Dict:
    """Sync updates for a specific project.

    Checks for new/updated issues and MRs since last sync.
    """
    logger.info(f"Syncing updates for project {project_id}")

    # This is a placeholder for incremental sync
    # Implementation would check last_indexed_at and fetch only newer items

    return {"status": "completed", "project_id": project_id}
