"""Indexing tasks for processing GitLab content."""

import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

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
            values["is_indexed"] = False

        session.execute(
            update(Project).where(Project.id == project_id).values(**values)
        )
        session.commit()


def run_async(coro):
    """Run async coroutine in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def index_project(self, project_id: int) -> Dict:
    """Index all content from a GitLab project.

    This task orchestrates the full indexing process by chaining subtasks.
    """
    logger.info(f"Starting indexing for project {project_id}")

    try:
        # Update status to indexing
        update_project_status(project_id, "indexing")

        # Get project info
        with get_sync_session() as session:
            project = session.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ValueError(f"Project {project_id} not found")
            gitlab_id = project.gitlab_id

        # Chain the indexing tasks
        # Use si() for first task (immutable - ignores any input)
        # Subsequent tasks receive previous result as first arg
        workflow = chain(
            fetch_and_index_readme.si(project_id, gitlab_id),
            fetch_and_index_issues.s(project_id, gitlab_id),
            fetch_and_index_merge_requests.s(project_id, gitlab_id),
            clone_and_index_code.s(project_id, gitlab_id),
            finalize_indexing.s(project_id),
        )

        result = workflow.apply_async()
        return {"status": "started", "task_id": str(result.id)}

    except Exception as exc:
        logger.error(f"Failed to start indexing for project {project_id}: {exc}")
        update_project_status(project_id, "error", str(exc))
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3)
def fetch_and_index_readme(self, project_id: int, gitlab_id: int) -> Dict:
    """Fetch and index the README.md file from the default branch."""
    logger.info(f"Indexing README for project {project_id}")

    try:
        gitlab = GitLabClient()
        chunker = ChunkingStrategy()
        embedder = EmbeddingService()

        # Get project info for default branch and name
        with get_sync_session() as session:
            project = session.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ValueError(f"Project {project_id} not found")
            default_branch = project.default_branch or "main"
            project_name = project.name
            web_url = f"{settings.gitlab_url}/{project.path_with_namespace}"

        readme_indexed = False

        # Try to fetch README.md (case-insensitive search)
        readme_files = ["README.md", "readme.md", "Readme.md", "README.MD"]

        for readme_file in readme_files:
            try:
                content = run_async(
                    gitlab.get_file_raw(gitlab_id, readme_file, ref=default_branch)
                )

                if content and content.strip():
                    # Chunk the README content
                    chunks = chunker.chunk_readme(
                        content, gitlab_id, project_name, web_url
                    )

                    if chunks:
                        point_ids = embedder.embed_chunks(chunks)

                        # Track indexed item
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
                                existing.qdrant_point_ids = point_ids
                                existing.indexed_at = datetime.utcnow()
                            else:
                                item = IndexedItem(
                                    project_id=project_id,
                                    item_type="readme",
                                    item_id=gitlab_id,
                                    qdrant_point_ids=point_ids,
                                )
                                session.add(item)
                            session.commit()

                        readme_indexed = True
                        logger.info(f"Indexed README.md for project {project_id}")
                        break

            except Exception as e:
                # File not found or other error, try next variant
                logger.debug(f"README file {readme_file} not found: {e}")
                continue

        if not readme_indexed:
            logger.info(f"No README.md found for project {project_id}")

        return {"readme_indexed": readme_indexed}

    except Exception as exc:
        logger.error(f"Failed to index README for project {project_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3)
def fetch_and_index_issues(self, previous_result: Dict, project_id: int, gitlab_id: int) -> Dict:
    """Fetch and index all issues for a project."""
    logger.info(f"Indexing issues for project {project_id}")

    try:
        gitlab = GitLabClient()
        chunker = ChunkingStrategy()
        embedder = EmbeddingService()

        issues_indexed = 0
        page = 1

        while True:
            # Fetch issues page
            issues = run_async(
                gitlab.get_issues(gitlab_id, page=page, per_page=100)
            )

            if not issues:
                break

            for issue in issues:
                try:
                    # Chunk issue content
                    chunks = chunker.chunk_issue(issue, gitlab_id)

                    # Fetch and chunk comments
                    notes = run_async(
                        gitlab.get_issue_notes(gitlab_id, issue["iid"])
                    )

                    for note in notes:
                        comment_chunks = chunker.chunk_comment(
                            note, "issue", issue["iid"], gitlab_id
                        )
                        chunks.extend(comment_chunks)

                    # Embed and store
                    if chunks:
                        point_ids = embedder.embed_chunks(chunks)

                        # Track indexed item
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
                                existing.qdrant_point_ids = point_ids
                                existing.indexed_at = datetime.utcnow()
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

                        issues_indexed += 1

                except Exception as e:
                    logger.warning(f"Failed to index issue {issue['iid']}: {e}")
                    continue

                # Rate limiting
                time.sleep(0.2)

            page += 1

            # Safety limit
            if page > 100:
                break

        logger.info(f"Indexed {issues_indexed} issues for project {project_id}")
        return {**previous_result, "issues_indexed": issues_indexed}

    except Exception as exc:
        logger.error(f"Failed to index issues for project {project_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3)
def fetch_and_index_merge_requests(
    self, previous_result: Dict, project_id: int, gitlab_id: int
) -> Dict:
    """Fetch and index all merge requests for a project."""
    logger.info(f"Indexing merge requests for project {project_id}")

    try:
        gitlab = GitLabClient()
        chunker = ChunkingStrategy()
        embedder = EmbeddingService()

        mrs_indexed = 0
        page = 1

        while True:
            # Fetch MRs page
            mrs = run_async(
                gitlab.get_merge_requests(gitlab_id, page=page, per_page=100)
            )

            if not mrs:
                break

            for mr in mrs:
                try:
                    # Chunk MR content
                    chunks = chunker.chunk_merge_request(mr, gitlab_id)

                    # Fetch and chunk comments
                    notes = run_async(gitlab.get_mr_notes(gitlab_id, mr["iid"]))

                    for note in notes:
                        comment_chunks = chunker.chunk_comment(
                            note, "merge_request", mr["iid"], gitlab_id
                        )
                        chunks.extend(comment_chunks)

                    # Embed and store
                    if chunks:
                        point_ids = embedder.embed_chunks(chunks)

                        # Track indexed item
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
                                existing.qdrant_point_ids = point_ids
                                existing.indexed_at = datetime.utcnow()
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

                        mrs_indexed += 1

                except Exception as e:
                    logger.warning(f"Failed to index MR {mr['iid']}: {e}")
                    continue

                # Rate limiting
                time.sleep(0.2)

            page += 1

            if page > 100:
                break

        logger.info(f"Indexed {mrs_indexed} merge requests for project {project_id}")
        return {**previous_result, "mrs_indexed": mrs_indexed}

    except Exception as exc:
        logger.error(f"Failed to index MRs for project {project_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3)
def clone_and_index_code(
    self, previous_result: Dict, project_id: int, gitlab_id: int
) -> Dict:
    """Clone repository and index code files."""
    logger.info(f"Indexing code for project {project_id}")

    try:
        # Get project info for cloning
        with get_sync_session() as session:
            project = session.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ValueError(f"Project {project_id} not found")
            project_data = {
                "gitlab_id": project.gitlab_id,
                "http_url_to_repo": project.http_url_to_repo,
            }

        agent = CodeAnalysisAgent()
        chunker = ChunkingStrategy()
        embedder = EmbeddingService()

        # Clone/update repository
        repo_path = run_async(agent.ensure_repo_cloned(project_data))

        if not repo_path.exists():
            logger.warning(f"Repository not cloned for project {project_id}")
            return {**previous_result, "code_indexed": False}

        files_indexed = 0
        all_point_ids = []

        # Index code files
        for file_path in repo_path.rglob("*"):
            if not file_path.is_file():
                continue

            if not _is_indexable_file(file_path, repo_path):
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                rel_path = str(file_path.relative_to(repo_path))

                chunks = chunker.chunk_code_file(rel_path, content, gitlab_id)

                if chunks:
                    point_ids = embedder.embed_chunks(chunks)
                    all_point_ids.extend(point_ids)
                    files_indexed += 1

            except Exception as e:
                logger.warning(f"Failed to index {file_path}: {e}")
                continue

        # Track code indexing
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
                existing.qdrant_point_ids = all_point_ids
                existing.indexed_at = datetime.utcnow()
            else:
                item = IndexedItem(
                    project_id=project_id,
                    item_type="code",
                    item_id=gitlab_id,
                    qdrant_point_ids=all_point_ids,
                )
                session.add(item)
            session.commit()

        logger.info(f"Indexed {files_indexed} code files for project {project_id}")
        return {**previous_result, "code_files_indexed": files_indexed}

    except Exception as exc:
        logger.error(f"Failed to index code for project {project_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task
def finalize_indexing(previous_result: Dict, project_id: int) -> Dict:
    """Finalize the indexing process."""
    logger.info(f"Finalizing indexing for project {project_id}")

    update_project_status(project_id, "completed")

    return {
        "status": "completed",
        "project_id": project_id,
        **previous_result,
    }


def _is_indexable_file(path: Path, repo_path: Path) -> bool:
    """Check if file should be indexed."""
    # Skip directories and patterns
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

    # Check if any parent directory should be skipped
    for part in path.relative_to(repo_path).parts:
        if part in skip_dirs:
            return False

    # Skip binary and non-code files
    skip_extensions = {
        ".pyc",
        ".pyo",
        ".so",
        ".dll",
        ".exe",
        ".bin",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".ico",
        ".svg",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".mp3",
        ".mp4",
        ".avi",
        ".mov",
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".zip",
        ".tar",
        ".gz",
        ".rar",
        ".7z",
        ".lock",
        ".min.js",
        ".min.css",
    }

    if path.suffix.lower() in skip_extensions:
        return False

    # Skip files that are too large (> 500KB)
    try:
        if path.stat().st_size > 500_000:
            return False
    except OSError:
        return False

    # Skip hidden files
    if path.name.startswith("."):
        return False

    return True
