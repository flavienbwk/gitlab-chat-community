"""GitLab API client."""

import asyncio
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config import get_settings


class GitLabClient:
    """Async client for GitLab API v4."""

    def __init__(self):
        settings = get_settings()
        self.base_url = settings.gitlab_url.rstrip("/")
        self.api_url = f"{self.base_url}/api/v4"
        self.pat = settings.gitlab_pat
        self.headers = {"PRIVATE-TOKEN": self.pat}
        self._last_request_time = 0
        self._min_request_interval = 0.1  # Rate limiting: 100ms between requests

    async def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            await asyncio.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        **kwargs,
    ) -> Any:
        """Make HTTP request to GitLab API."""
        await self._rate_limit()

        url = f"{self.api_url}{endpoint}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method, url, headers=self.headers, params=params, **kwargs
            )
            response.raise_for_status()
            return response.json()

    async def _paginate(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        max_pages: int = 100,
    ) -> List[Dict]:
        """Paginate through all results."""
        params = params or {}
        params.setdefault("per_page", 100)
        params.setdefault("page", 1)

        all_results = []
        for _ in range(max_pages):
            results = await self._request("GET", endpoint, params=params)
            if not results:
                break
            all_results.extend(results)
            if len(results) < params["per_page"]:
                break
            params["page"] += 1

        return all_results

    # Projects API
    async def get_projects(self, membership: bool = True) -> List[Dict]:
        """Get all accessible projects."""
        params = {"membership": str(membership).lower(), "per_page": 100}
        return await self._paginate("/projects", params)

    async def get_project(self, project_id: int) -> Dict:
        """Get single project details."""
        return await self._request("GET", f"/projects/{project_id}")

    # Issues API
    async def get_issues(
        self,
        project_id: int,
        state: str = "all",
        labels: Optional[List[str]] = None,
        search: Optional[str] = None,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
        updated_after: Optional[str] = None,
        updated_before: Optional[str] = None,
        page: int = 1,
        per_page: int = 100,
    ) -> List[Dict]:
        """Get project issues with filters."""
        params = {
            "state": state,
            "per_page": per_page,
            "page": page,
            "order_by": "updated_at",
            "sort": "desc",
        }
        if labels:
            params["labels"] = ",".join(labels)
        if search:
            params["search"] = search
        if created_after:
            params["created_after"] = created_after
        if created_before:
            params["created_before"] = created_before
        if updated_after:
            params["updated_after"] = updated_after
        if updated_before:
            params["updated_before"] = updated_before

        return await self._request(
            "GET", f"/projects/{project_id}/issues", params=params
        )

    async def get_all_issues(self, project_id: int, **kwargs) -> List[Dict]:
        """Get all issues for a project with pagination."""
        params = {"state": "all", "per_page": 100, **kwargs}
        return await self._paginate(f"/projects/{project_id}/issues", params)

    async def get_issue_ids(self, project_id: int) -> List[int]:
        """Get all issue IDs for a project (for deletion detection)."""
        params = {"state": "all", "per_page": 100}
        issues = await self._paginate(f"/projects/{project_id}/issues", params)
        return [issue["id"] for issue in issues]

    async def get_issue(self, project_id: int, issue_iid: int) -> Dict:
        """Get single issue."""
        return await self._request(
            "GET", f"/projects/{project_id}/issues/{issue_iid}"
        )

    async def get_issue_notes(
        self, project_id: int, issue_iid: int
    ) -> List[Dict]:
        """Get all notes/comments for an issue."""
        return await self._paginate(
            f"/projects/{project_id}/issues/{issue_iid}/notes",
            {"sort": "asc", "order_by": "created_at"},
        )

    async def get_issue_discussions(
        self, project_id: int, issue_iid: int
    ) -> List[Dict]:
        """Get threaded discussions for an issue."""
        return await self._paginate(
            f"/projects/{project_id}/issues/{issue_iid}/discussions"
        )

    # Merge Requests API
    async def get_merge_requests(
        self,
        project_id: int,
        state: str = "all",
        labels: Optional[List[str]] = None,
        search: Optional[str] = None,
        updated_after: Optional[str] = None,
        updated_before: Optional[str] = None,
        page: int = 1,
        per_page: int = 100,
    ) -> List[Dict]:
        """Get project merge requests with filters."""
        params = {
            "state": state,
            "per_page": per_page,
            "page": page,
            "order_by": "updated_at",
            "sort": "desc",
        }
        if labels:
            params["labels"] = ",".join(labels)
        if search:
            params["search"] = search
        if updated_after:
            params["updated_after"] = updated_after
        if updated_before:
            params["updated_before"] = updated_before

        return await self._request(
            "GET", f"/projects/{project_id}/merge_requests", params=params
        )

    async def get_all_merge_requests(self, project_id: int, **kwargs) -> List[Dict]:
        """Get all merge requests for a project with pagination."""
        params = {"state": "all", "per_page": 100, **kwargs}
        return await self._paginate(f"/projects/{project_id}/merge_requests", params)

    async def get_mr_ids(self, project_id: int) -> List[int]:
        """Get all merge request IDs for a project (for deletion detection)."""
        params = {"state": "all", "per_page": 100}
        mrs = await self._paginate(f"/projects/{project_id}/merge_requests", params)
        return [mr["id"] for mr in mrs]

    async def get_merge_request(self, project_id: int, mr_iid: int) -> Dict:
        """Get single merge request."""
        return await self._request(
            "GET", f"/projects/{project_id}/merge_requests/{mr_iid}"
        )

    async def get_mr_notes(self, project_id: int, mr_iid: int) -> List[Dict]:
        """Get all notes/comments for a merge request."""
        return await self._paginate(
            f"/projects/{project_id}/merge_requests/{mr_iid}/notes",
            {"sort": "asc", "order_by": "created_at"},
        )

    async def get_mr_discussions(self, project_id: int, mr_iid: int) -> List[Dict]:
        """Get threaded discussions for a merge request."""
        return await self._paginate(
            f"/projects/{project_id}/merge_requests/{mr_iid}/discussions"
        )

    async def get_mr_diffs(self, project_id: int, mr_iid: int) -> List[Dict]:
        """Get merge request diffs/changes."""
        return await self._request(
            "GET", f"/projects/{project_id}/merge_requests/{mr_iid}/diffs"
        )

    # Repository API
    async def get_repository_tree(
        self,
        project_id: int,
        path: str = "",
        ref: str = "main",
        recursive: bool = True,
    ) -> List[Dict]:
        """Get repository file tree."""
        params = {"ref": ref, "recursive": str(recursive).lower(), "per_page": 100}
        if path:
            params["path"] = path
        return await self._paginate(
            f"/projects/{project_id}/repository/tree", params
        )

    async def get_file_content(
        self, project_id: int, file_path: str, ref: str = "main"
    ) -> Dict:
        """Get file content (base64 encoded)."""
        encoded_path = quote(file_path, safe="")
        return await self._request(
            "GET",
            f"/projects/{project_id}/repository/files/{encoded_path}",
            params={"ref": ref},
        )

    async def get_file_raw(
        self, project_id: int, file_path: str, ref: str = "main"
    ) -> str:
        """Get raw file content."""
        await self._rate_limit()
        encoded_path = quote(file_path, safe="")
        url = f"{self.api_url}/projects/{project_id}/repository/files/{encoded_path}/raw"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url, headers=self.headers, params={"ref": ref}
            )
            response.raise_for_status()
            return response.text
