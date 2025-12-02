"""Project API routes."""

from datetime import datetime
from typing import List, Optional

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_serializer

from api.dependencies import get_gitlab_client, get_project_repo
from core.embedding import EmbeddingService
from core.gitlab_client import GitLabClient
from db.repositories import ProjectRepository
from tasks.celery_app import celery_app
from tasks.indexing import index_project
from tasks.sync import refresh_projects, sync_project

router = APIRouter()


class ProjectResponse(BaseModel):
    """Project response model."""

    id: int
    gitlab_id: int
    name: str
    path_with_namespace: str
    description: Optional[str] = None
    default_branch: str
    is_indexed: bool
    is_selected: bool
    indexing_status: str
    indexing_error: Optional[str] = None
    last_indexed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_serializer('last_indexed_at')
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        return value.isoformat()


class ProjectListResponse(BaseModel):
    """Project list response."""

    projects: List[ProjectResponse]
    total: int


class VectorCountsResponse(BaseModel):
    """Vector counts per project."""

    counts: dict[int, int]
    total: int


class IndexingStatusResponse(BaseModel):
    """Indexing status response."""

    status: str
    error: Optional[str] = None
    is_indexed: bool


@router.get("/projects", response_model=ProjectListResponse)
async def list_projects(
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    """List all projects."""
    projects = await project_repo.get_all()
    return ProjectListResponse(
        projects=[ProjectResponse.model_validate(p) for p in projects],
        total=len(projects),
    )


@router.get("/projects/vector-counts", response_model=VectorCountsResponse)
async def get_vector_counts():
    """Get vector counts per project from Qdrant."""
    embedding_service = EmbeddingService()
    counts = embedding_service.get_all_project_counts()
    return VectorCountsResponse(
        counts=counts,
        total=sum(counts.values()),
    )


@router.post("/projects/refresh")
async def refresh_project_list(
    project_repo: ProjectRepository = Depends(get_project_repo),
    gitlab: GitLabClient = Depends(get_gitlab_client),
):
    """Refresh project list from GitLab.

    This fetches projects synchronously for immediate feedback,
    or can be run as a background task for larger instances.
    """
    try:
        # Fetch projects from GitLab
        gitlab_projects = await gitlab.get_projects(membership=True)

        created = 0
        updated = 0

        for proj in gitlab_projects:
            existing = await project_repo.get_by_gitlab_id(proj["id"])

            if existing:
                # Update existing
                await project_repo.upsert(
                    gitlab_id=proj["id"],
                    name=proj["name"],
                    path_with_namespace=proj["path_with_namespace"],
                    description=proj.get("description"),
                    default_branch=proj.get("default_branch", "main"),
                    http_url_to_repo=proj.get("http_url_to_repo"),
                )
                updated += 1
            else:
                # Create new
                await project_repo.create(
                    gitlab_id=proj["id"],
                    name=proj["name"],
                    path_with_namespace=proj["path_with_namespace"],
                    description=proj.get("description"),
                    default_branch=proj.get("default_branch", "main"),
                    http_url_to_repo=proj.get("http_url_to_repo"),
                )
                created += 1

        return {
            "status": "completed",
            "total": len(gitlab_projects),
            "created": created,
            "updated": updated,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    """Get a specific project."""
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse.model_validate(project)


@router.post("/projects/{project_id}/select")
async def select_project(
    project_id: int,
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    """Select a project for querying."""
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await project_repo.set_selected(project_id, True)
    return {"status": "selected", "project_id": project_id}


@router.post("/projects/{project_id}/deselect")
async def deselect_project(
    project_id: int,
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    """Deselect a project from querying."""
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await project_repo.set_selected(project_id, False)
    return {"status": "deselected", "project_id": project_id}


@router.post("/projects/{project_id}/index")
async def trigger_indexing(
    project_id: int,
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    """Trigger full indexing for a project.

    This performs a complete re-index of all issues, MRs, and code.
    For incremental updates, use /sync instead.
    """
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if already indexing
    if project.indexing_status in ("indexing", "syncing"):
        return {
            "status": "already_indexing",
            "project_id": project_id,
            "message": "Project is already being indexed or synced",
        }

    # Trigger async indexing task
    task = index_project.delay(project_id)

    return {
        "status": "started",
        "project_id": project_id,
        "task_id": str(task.id),
        "mode": "full",
    }


@router.post("/projects/{project_id}/sync")
async def trigger_sync(
    project_id: int,
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    """Trigger incremental sync for a project.

    This only indexes new/updated issues, MRs, and code changes since
    the last indexing. Much faster than full indexing for active projects.

    If the project has never been indexed, this will trigger a full index.
    """
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if already indexing/syncing
    if project.indexing_status in ("indexing", "syncing"):
        return {
            "status": "already_indexing",
            "project_id": project_id,
            "message": "Project is already being indexed or synced",
        }

    # If never indexed, inform user that full index will run
    mode = "incremental" if project.is_indexed else "full"

    # Trigger async sync task
    task = sync_project.delay(project_id)

    return {
        "status": "started",
        "project_id": project_id,
        "task_id": str(task.id),
        "mode": mode,
        "message": "Incremental sync started" if mode == "incremental" else "Full index started (project was never indexed)",
    }


@router.get("/projects/{project_id}/status", response_model=IndexingStatusResponse)
async def get_indexing_status(
    project_id: int,
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    """Get indexing status for a project."""
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return IndexingStatusResponse(
        status=project.indexing_status,
        error=project.indexing_error,
        is_indexed=project.is_indexed,
    )


@router.get("/projects/selected/list", response_model=ProjectListResponse)
async def list_selected_projects(
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    """List selected projects."""
    projects = await project_repo.get_selected()
    return ProjectListResponse(
        projects=[ProjectResponse.model_validate(p) for p in projects],
        total=len(projects),
    )


@router.post("/projects/{project_id}/stop-indexing")
async def stop_indexing(
    project_id: int,
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    """Stop indexing for a project and revoke any pending tasks."""
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.indexing_status not in ("indexing", "syncing"):
        return {
            "status": "not_indexing",
            "project_id": project_id,
            "message": "Project is not currently being indexed or synced",
        }

    # Revoke all tasks for this project
    # Note: This uses Celery's revoke which sends SIGTERM to running tasks
    inspector = celery_app.control.inspect()
    active_tasks = inspector.active() or {}
    reserved_tasks = inspector.reserved() or {}

    revoked_count = 0
    for worker_tasks in list(active_tasks.values()) + list(reserved_tasks.values()):
        for task in worker_tasks:
            # Check if task is related to this project
            task_args = task.get("args", [])
            if project_id in task_args or str(project_id) in str(task_args):
                celery_app.control.revoke(task["id"], terminate=True)
                revoked_count += 1

    # Update project status
    await project_repo.update_status(project_id, "stopped", "Indexing stopped by user")

    return {
        "status": "stopped",
        "project_id": project_id,
        "revoked_tasks": revoked_count,
    }


@router.post("/projects/{project_id}/clear-index")
async def clear_project_index(
    project_id: int,
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    """Clear all indexed data for a project from the vector database."""
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Don't allow clearing while indexing
    if project.indexing_status == "indexing":
        raise HTTPException(
            status_code=400,
            detail="Cannot clear index while indexing is in progress. Stop indexing first.",
        )

    try:
        # Delete vectors from Qdrant
        embedding_service = EmbeddingService()
        embedding_service.delete_by_project(project.gitlab_id)

        # Reset project indexing status
        await project_repo.update_status(project_id, "pending", None)

        # Clear indexed items from database
        from db.database import get_db
        from db.repositories import IndexedItemRepository

        async for session in get_db():
            indexed_repo = IndexedItemRepository(session)
            await indexed_repo.delete_by_project(project_id)
            await session.commit()
            break

        return {
            "status": "cleared",
            "project_id": project_id,
            "message": "All indexed data has been removed",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear index: {str(e)}")
