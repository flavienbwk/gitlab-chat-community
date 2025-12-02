"""GitLab synchronization tasks with incremental indexing."""

import asyncio
import hashlib
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set

from celery import chain, shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import create_engine, update
from sqlalchemy.orm import Session

from config import get_settings
from core.chunking import ChunkingStrategy
from core.code_analysis import CodeAnalysisAgent
from core.embedding import EmbeddingService
from core.gitlab_client import GitLabClient
from db.models import IndexedItem, Project

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


def update_project_status(
    project_id: int, status: str, error: Optional[str] = None
) -> None:
    """Update project indexing status."""
    with get_sync_session() as session:
        values = {"indexing_status": status, "indexing_error": error}
        if status == "completed":
            values["is_indexed"] = True
            values["last_indexed_at"] = datetime.utcnow()
        elif status == "error":
            pass  # Keep is_indexed as-is for sync errors

        session.execute(
            update(Project).where(Project.id == project_id).values(**values)
        )
        session.commit()


@shared_task(bind=True)
def sync_all_indexed_projects(self) -> Dict:
    """Sync all successfully indexed projects.

    This task is triggered periodically by Celery Beat to keep
    indexed projects up to date with GitLab.
    """
    logger.info("Starting periodic sync of all indexed projects")

    try:
        with get_sync_session() as session:
            # Find all projects that are successfully indexed and not currently syncing
            projects = (
                session.query(Project)
                .filter(
                    Project.is_indexed == True,
                    Project.indexing_status.in_(["completed", "error"]),
                )
                .all()
            )

            project_ids = [p.id for p in projects]

            # Also recover any projects stuck in "syncing" for more than 2 minutes
            # This handles cases where a sync task was killed mid-execution
            stale_threshold = datetime.utcnow() - timedelta(minutes=2)
            stale_projects = (
                session.query(Project)
                .filter(
                    Project.is_indexed == True,
                    Project.indexing_status == "syncing",
                    Project.last_indexed_at < stale_threshold,
                )
                .all()
            )

            if stale_projects:
                stale_ids = [p.id for p in stale_projects]
                logger.warning(f"Recovering {len(stale_ids)} stale syncing projects: {stale_ids}")
                # Reset their status so they can be synced
                for project in stale_projects:
                    project.indexing_status = "completed"
                session.commit()
                project_ids.extend(stale_ids)

        if not project_ids:
            logger.info("No indexed projects to sync")
            return {"status": "completed", "projects_synced": 0}

        logger.info(f"Queuing sync for {len(project_ids)} indexed projects")

        # Queue sync for each project
        for project_id in project_ids:
            sync_project.delay(project_id)

        return {
            "status": "completed",
            "projects_synced": len(project_ids),
            "project_ids": project_ids,
        }

    except Exception as exc:
        logger.error(f"Failed to queue periodic sync: {exc}")
        return {"status": "error", "error": str(exc)}


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


# =============================================================================
# INCREMENTAL SYNC TASKS
# =============================================================================


@shared_task(bind=True)
def handle_sync_error(self, request, exc, traceback, project_id: int) -> Dict:
    """Handle sync chain errors by resetting project status."""
    logger.error(f"Sync chain failed for project {project_id}: {exc}")
    update_project_status(project_id, "error", str(exc))
    return {"status": "error", "error": str(exc), "project_id": project_id}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_project(self, project_id: int) -> Dict:
    """Incrementally sync a project - only index new/changed content.

    This is much faster than full re-indexing as it:
    1. Only fetches issues/MRs updated since last_indexed_at
    2. Uses git pull + diff to find changed code files
    3. Detects deleted items and removes their vectors
    """
    logger.info(f"Starting incremental sync for project {project_id}")

    try:
        update_project_status(project_id, "syncing")

        # Get project info
        with get_sync_session() as session:
            project = session.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ValueError(f"Project {project_id} not found")
            gitlab_id = project.gitlab_id
            last_indexed_at = project.last_indexed_at

        if not last_indexed_at:
            # Never indexed before, do full index instead
            logger.info(f"Project {project_id} never indexed, triggering full index")
            from tasks.indexing import index_project
            return index_project.delay(project_id).get()

        # Chain incremental sync tasks with error handler
        workflow = chain(
            sync_readme.si(project_id, gitlab_id),
            sync_issues_incremental.s(project_id, gitlab_id, last_indexed_at.isoformat()),
            sync_mrs_incremental.s(project_id, gitlab_id, last_indexed_at.isoformat()),
            sync_code_incremental.s(project_id, gitlab_id),
            cleanup_deleted_items.s(project_id, gitlab_id),
            finalize_sync.s(project_id),
        )

        # Apply with error callback to reset status on failure
        result = workflow.apply_async(
            link_error=handle_sync_error.s(project_id)
        )
        return {"status": "started", "task_id": str(result.id)}

    except Exception as exc:
        logger.error(f"Failed to sync project {project_id}: {exc}")
        update_project_status(project_id, "error", str(exc))
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3)
def sync_readme(self, project_id: int, gitlab_id: int) -> Dict:
    """Sync README - always re-check as it's a single cheap operation."""
    logger.info(f"Syncing README for project {project_id}")

    try:
        gitlab = GitLabClient()
        chunker = ChunkingStrategy()
        embedder = EmbeddingService()

        # Get project info
        with get_sync_session() as session:
            project = session.query(Project).filter(Project.id == project_id).first()
            default_branch = project.default_branch or "main"
            project_name = project.name
            web_url = f"{settings.gitlab_url}/{project.path_with_namespace}"

        readme_files = ["README.md", "readme.md", "Readme.md", "README.MD"]
        content_hash = None
        new_content = None

        for readme_file in readme_files:
            try:
                content = run_async(
                    gitlab.get_file_raw(gitlab_id, readme_file, ref=default_branch)
                )
                if content and content.strip():
                    new_content = content
                    content_hash = hashlib.sha256(content.encode()).hexdigest()
                    break
            except Exception:
                continue

        if not new_content:
            logger.info(f"No README found for project {project_id}")
            return {"readme_updated": False}

        # Check if README changed by comparing hash
        with get_sync_session() as session:
            existing = (
                session.query(IndexedItem)
                .filter(
                    IndexedItem.project_id == project_id,
                    IndexedItem.item_type == "readme",
                )
                .first()
            )

            # Store hash in item_iid field (repurposed for README)
            old_hash = str(existing.item_iid) if existing and existing.item_iid else None

        if old_hash == content_hash:
            logger.info(f"README unchanged for project {project_id}")
            return {"readme_updated": False}

        # README changed, re-index it
        chunks = chunker.chunk_readme(new_content, gitlab_id, project_name, web_url)

        if chunks:
            point_ids = embedder.embed_chunks(chunks)

            with get_sync_session() as session:
                existing = (
                    session.query(IndexedItem)
                    .filter(
                        IndexedItem.project_id == project_id,
                        IndexedItem.item_type == "readme",
                    )
                    .first()
                )

                if existing:
                    # Delete old points if they exist
                    if existing.qdrant_point_ids:
                        embedder.delete_by_ids(existing.qdrant_point_ids)
                    existing.qdrant_point_ids = point_ids
                    existing.indexed_at = datetime.utcnow()
                    # Store hash for future comparison (using item_iid)
                    existing.item_iid = int(content_hash[:8], 16)  # Store partial hash
                else:
                    item = IndexedItem(
                        project_id=project_id,
                        item_type="readme",
                        item_id=gitlab_id,
                        item_iid=int(content_hash[:8], 16),
                        qdrant_point_ids=point_ids,
                    )
                    session.add(item)
                session.commit()

            logger.info(f"README updated for project {project_id}")
            return {"readme_updated": True}

        return {"readme_updated": False}

    except Exception as exc:
        logger.error(f"Failed to sync README for project {project_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3)
def sync_issues_incremental(
    self, previous_result: Dict, project_id: int, gitlab_id: int, since_iso: str
) -> Dict:
    """Sync only issues updated since last index."""
    logger.info(f"Syncing issues updated since {since_iso} for project {project_id}")

    try:
        gitlab = GitLabClient()
        chunker = ChunkingStrategy()
        embedder = EmbeddingService()

        issues_updated = 0
        page = 1

        while True:
            # Fetch only issues updated after last index
            issues = run_async(
                gitlab.get_issues(
                    gitlab_id,
                    page=page,
                    per_page=100,
                    updated_after=since_iso,
                )
            )

            if not issues:
                break

            for issue in issues:
                try:
                    # Re-index this issue (chunks + comments)
                    chunks = chunker.chunk_issue(issue, gitlab_id)

                    notes = run_async(
                        gitlab.get_issue_notes(gitlab_id, issue["iid"])
                    )
                    for note in notes:
                        comment_chunks = chunker.chunk_comment(
                            note, "issue", issue["iid"], gitlab_id
                        )
                        chunks.extend(comment_chunks)

                    if chunks:
                        point_ids = embedder.embed_chunks(chunks)

                        with get_sync_session() as session:
                            existing = (
                                session.query(IndexedItem)
                                .filter(
                                    IndexedItem.project_id == project_id,
                                    IndexedItem.item_type == "issue",
                                    IndexedItem.item_id == issue["id"],
                                )
                                .first()
                            )

                            if existing:
                                # Delete old points and update
                                if existing.qdrant_point_ids:
                                    embedder.delete_by_ids(existing.qdrant_point_ids)
                                existing.qdrant_point_ids = point_ids
                                existing.indexed_at = datetime.utcnow()
                                existing.last_updated_at = datetime.fromisoformat(
                                    issue["updated_at"].replace("Z", "+00:00")
                                )
                            else:
                                item = IndexedItem(
                                    project_id=project_id,
                                    item_type="issue",
                                    item_id=issue["id"],
                                    item_iid=issue["iid"],
                                    qdrant_point_ids=point_ids,
                                    last_updated_at=datetime.fromisoformat(
                                        issue["updated_at"].replace("Z", "+00:00")
                                    ),
                                )
                                session.add(item)
                            session.commit()

                        issues_updated += 1

                except Exception as e:
                    logger.warning(f"Failed to sync issue {issue['iid']}: {e}")
                    continue

                time.sleep(0.2)

            page += 1
            if page > 100:
                break

        logger.info(f"Synced {issues_updated} updated issues for project {project_id}")
        return {**previous_result, "issues_updated": issues_updated}

    except Exception as exc:
        logger.error(f"Failed to sync issues for project {project_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3)
def sync_mrs_incremental(
    self, previous_result: Dict, project_id: int, gitlab_id: int, since_iso: str
) -> Dict:
    """Sync only MRs updated since last index."""
    logger.info(f"Syncing MRs updated since {since_iso} for project {project_id}")

    try:
        gitlab = GitLabClient()
        chunker = ChunkingStrategy()
        embedder = EmbeddingService()

        mrs_updated = 0
        page = 1

        while True:
            mrs = run_async(
                gitlab.get_merge_requests(
                    gitlab_id,
                    page=page,
                    per_page=100,
                    updated_after=since_iso,
                )
            )

            if not mrs:
                break

            for mr in mrs:
                try:
                    chunks = chunker.chunk_merge_request(mr, gitlab_id)

                    notes = run_async(gitlab.get_mr_notes(gitlab_id, mr["iid"]))
                    for note in notes:
                        comment_chunks = chunker.chunk_comment(
                            note, "merge_request", mr["iid"], gitlab_id
                        )
                        chunks.extend(comment_chunks)

                    if chunks:
                        point_ids = embedder.embed_chunks(chunks)

                        with get_sync_session() as session:
                            existing = (
                                session.query(IndexedItem)
                                .filter(
                                    IndexedItem.project_id == project_id,
                                    IndexedItem.item_type == "merge_request",
                                    IndexedItem.item_id == mr["id"],
                                )
                                .first()
                            )

                            if existing:
                                if existing.qdrant_point_ids:
                                    embedder.delete_by_ids(existing.qdrant_point_ids)
                                existing.qdrant_point_ids = point_ids
                                existing.indexed_at = datetime.utcnow()
                                existing.last_updated_at = datetime.fromisoformat(
                                    mr["updated_at"].replace("Z", "+00:00")
                                )
                            else:
                                item = IndexedItem(
                                    project_id=project_id,
                                    item_type="merge_request",
                                    item_id=mr["id"],
                                    item_iid=mr["iid"],
                                    qdrant_point_ids=point_ids,
                                    last_updated_at=datetime.fromisoformat(
                                        mr["updated_at"].replace("Z", "+00:00")
                                    ),
                                )
                                session.add(item)
                            session.commit()

                        mrs_updated += 1

                except Exception as e:
                    logger.warning(f"Failed to sync MR {mr['iid']}: {e}")
                    continue

                time.sleep(0.2)

            page += 1
            if page > 100:
                break

        logger.info(f"Synced {mrs_updated} updated MRs for project {project_id}")
        return {**previous_result, "mrs_updated": mrs_updated}

    except Exception as exc:
        logger.error(f"Failed to sync MRs for project {project_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3)
def sync_code_incremental(
    self, previous_result: Dict, project_id: int, gitlab_id: int
) -> Dict:
    """Sync code changes using git pull + diff."""
    logger.info(f"Syncing code changes for project {project_id}")

    try:
        # Get project info
        with get_sync_session() as session:
            project = session.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ValueError(f"Project {project_id} not found")
            last_commit = project.last_indexed_commit
            project_data = {
                "gitlab_id": project.gitlab_id,
                "http_url_to_repo": project.http_url_to_repo,
            }

        agent = CodeAnalysisAgent()
        chunker = ChunkingStrategy()
        embedder = EmbeddingService()

        # Ensure repo is cloned
        repo_path = run_async(agent.ensure_repo_cloned(project_data))

        if not repo_path.exists():
            logger.warning(f"Repository not found for project {project_id}")
            return {**previous_result, "code_files_updated": 0}

        # Get current commit before pull
        old_head = _get_git_head(repo_path)

        # Pull latest changes
        _git_pull(repo_path)

        # Get new commit
        new_head = _get_git_head(repo_path)

        if old_head == new_head and last_commit == new_head:
            logger.info(f"No code changes for project {project_id}")
            return {**previous_result, "code_files_updated": 0}

        # Find changed files since last indexed commit
        base_commit = last_commit or old_head
        changed_files = _get_changed_files(repo_path, base_commit, new_head)

        logger.info(f"Found {len(changed_files)} changed files")

        files_updated = 0
        all_point_ids = []

        for rel_path in changed_files:
            file_path = repo_path / rel_path

            if not file_path.exists():
                # File was deleted, skip (handled by cleanup task)
                continue

            if not _is_indexable_file(file_path, repo_path):
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                chunks = chunker.chunk_code_file(rel_path, content, gitlab_id)

                if chunks:
                    point_ids = embedder.embed_chunks(chunks)
                    all_point_ids.extend(point_ids)
                    files_updated += 1

            except Exception as e:
                logger.warning(f"Failed to index {rel_path}: {e}")
                continue

        # Update code tracking
        with get_sync_session() as session:
            existing = (
                session.query(IndexedItem)
                .filter(
                    IndexedItem.project_id == project_id,
                    IndexedItem.item_type == "code",
                )
                .first()
            )

            if existing:
                # Merge new point IDs with existing (upsert handles duplicates)
                existing.qdrant_point_ids = list(
                    set(existing.qdrant_point_ids or []) | set(all_point_ids)
                )
                existing.indexed_at = datetime.utcnow()
            else:
                item = IndexedItem(
                    project_id=project_id,
                    item_type="code",
                    item_id=gitlab_id,
                    qdrant_point_ids=all_point_ids,
                )
                session.add(item)

            # Update last indexed commit
            session.execute(
                update(Project)
                .where(Project.id == project_id)
                .values(last_indexed_commit=new_head)
            )
            session.commit()

        logger.info(f"Synced {files_updated} code files for project {project_id}")
        return {**previous_result, "code_files_updated": files_updated}

    except Exception as exc:
        logger.error(f"Failed to sync code for project {project_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3)
def cleanup_deleted_items(
    self, previous_result: Dict, project_id: int, gitlab_id: int
) -> Dict:
    """Remove vectors for deleted issues/MRs."""
    logger.info(f"Cleaning up deleted items for project {project_id}")

    try:
        gitlab = GitLabClient()
        embedder = EmbeddingService()

        # Get current issue/MR IDs from GitLab
        current_issue_ids = set(run_async(gitlab.get_issue_ids(gitlab_id)))
        current_mr_ids = set(run_async(gitlab.get_mr_ids(gitlab_id)))

        deleted_issues = 0
        deleted_mrs = 0

        with get_sync_session() as session:
            # Find indexed issues that no longer exist
            indexed_issues = (
                session.query(IndexedItem)
                .filter(
                    IndexedItem.project_id == project_id,
                    IndexedItem.item_type == "issue",
                )
                .all()
            )

            for item in indexed_issues:
                if item.item_id not in current_issue_ids:
                    # Issue was deleted
                    if item.qdrant_point_ids:
                        embedder.delete_by_ids(item.qdrant_point_ids)
                    session.delete(item)
                    deleted_issues += 1

            # Find indexed MRs that no longer exist
            indexed_mrs = (
                session.query(IndexedItem)
                .filter(
                    IndexedItem.project_id == project_id,
                    IndexedItem.item_type == "merge_request",
                )
                .all()
            )

            for item in indexed_mrs:
                if item.item_id not in current_mr_ids:
                    # MR was deleted
                    if item.qdrant_point_ids:
                        embedder.delete_by_ids(item.qdrant_point_ids)
                    session.delete(item)
                    deleted_mrs += 1

            session.commit()

        logger.info(
            f"Cleaned up {deleted_issues} issues, {deleted_mrs} MRs for project {project_id}"
        )
        return {
            **previous_result,
            "deleted_issues": deleted_issues,
            "deleted_mrs": deleted_mrs,
        }

    except Exception as exc:
        logger.error(f"Failed to cleanup deleted items for project {project_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True)
def finalize_sync(self, previous_result: Dict, project_id: int) -> Dict:
    """Finalize the sync process."""
    logger.info(f"Finalizing sync for project {project_id}")

    # Check if previous result indicates an error
    if isinstance(previous_result, dict) and previous_result.get("status") == "error":
        update_project_status(project_id, "error", previous_result.get("error"))
        return previous_result

    update_project_status(project_id, "completed")

    return {
        "status": "completed",
        "project_id": project_id,
        **previous_result,
    }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _get_git_head(repo_path: Path) -> str:
    """Get current HEAD commit SHA."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _git_pull(repo_path: Path) -> bool:
    """Pull latest changes."""
    result = subprocess.run(
        ["git", "pull", "--ff-only"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _get_changed_files(repo_path: Path, old_commit: str, new_commit: str) -> List[str]:
    """Get list of files changed between two commits."""
    if not old_commit:
        # If no old commit, return empty (will be handled by full index)
        return []

    result = subprocess.run(
        ["git", "diff", "--name-only", old_commit, new_commit],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return []

    return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]


def _is_indexable_file(path: Path, repo_path: Path) -> bool:
    """Check if file should be indexed."""
    skip_dirs = {
        ".git",
        "node_modules",
        "__pycache__",
        "venv",
        ".venv",
        "dist",
        "build",
        ".next",
        "coverage",
        ".cache",
        "vendor",
        "target",
    }

    for part in path.relative_to(repo_path).parts:
        if part in skip_dirs:
            return False

    skip_extensions = {
        ".pyc", ".pyo", ".so", ".dll", ".exe", ".bin",
        ".jpg", ".jpeg", ".png", ".gif", ".ico", ".svg",
        ".woff", ".woff2", ".ttf", ".eot",
        ".mp3", ".mp4", ".avi", ".mov",
        ".pdf", ".doc", ".docx", ".xls", ".xlsx",
        ".zip", ".tar", ".gz", ".rar", ".7z",
        ".lock", ".min.js", ".min.css",
    }

    if path.suffix.lower() in skip_extensions:
        return False

    try:
        if path.stat().st_size > 500_000:
            return False
    except OSError:
        return False

    if path.name.startswith("."):
        return False

    return True
