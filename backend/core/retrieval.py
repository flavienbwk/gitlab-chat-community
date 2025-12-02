"""Hybrid retrieval combining vector search and structured filters."""

import json
from typing import Any, Dict, List, Optional

from openai import OpenAI

from config import get_settings
from core.embedding import EmbeddingService
from core.gitlab_client import GitLabClient


class HybridRetriever:
    """Combines vector search with GitLab API queries."""

    FILTER_EXTRACTION_PROMPT = """You are a query analyzer for a GitLab search system. Extract structured filters from the user's natural language query.

Return a JSON object with these optional fields:
- "labels": list of label names mentioned (e.g., ["bug", "feature"])
- "state": issue/MR state ("opened", "closed", "merged", "all")
- "search_terms": key search terms for text matching
- "date_filter": object with "after" and/or "before" dates (ISO format)
- "content_types": list of content types to search ("issue", "merge_request", "code", "comment")
- "issue_iid": specific issue number if mentioned
- "mr_iid": specific MR number if mentioned
- "needs_api_query": boolean - true if query requires fresh data from GitLab API

Examples:
Query: "Issues labeled 'bug' created last month"
Output: {"labels": ["bug"], "date_filter": {"after": "2024-01-01"}, "content_types": ["issue"]}

Query: "What is issue #123 about?"
Output: {"issue_iid": 123, "content_types": ["issue"], "needs_api_query": true}

Query: "Code that handles authentication"
Output: {"search_terms": "authentication", "content_types": ["code"]}

Query: "Recent merge requests by John"
Output: {"content_types": ["merge_request"], "search_terms": "John"}

Now analyze this query and return only the JSON object:
Query: "{query}"
"""

    def __init__(self):
        settings = get_settings()
        self.embedding_service = EmbeddingService()
        self.gitlab_client = GitLabClient()
        # Only pass base_url if it's actually set (not empty string)
        base_url = settings.openai_base_url if settings.openai_base_url else None
        self.openai = OpenAI(api_key=settings.openai_api_key, base_url=base_url)
        self.model = settings.openai_model
        self.top_k = settings.top_k_results

    async def extract_filters(self, query: str) -> Dict[str, Any]:
        """Use LLM to extract structured filters from query."""
        try:
            response = self.openai.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": self.FILTER_EXTRACTION_PROMPT.format(query=query),
                    }
                ],
                temperature=0,
                max_tokens=500,
            )

            content = response.choices[0].message.content.strip()

            # Extract JSON from response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            return json.loads(content)
        except (json.JSONDecodeError, Exception):
            # Fallback to no filters
            return {}

    async def retrieve(
        self,
        query: str,
        project_ids: Optional[List[int]] = None,
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Perform hybrid retrieval combining vector search and API queries."""
        top_k = top_k or self.top_k
        results = []

        # Extract filters from query
        filters = await self.extract_filters(query)

        # Determine content types to search
        content_types = filters.get("content_types")

        # 1. Vector search for semantic matching
        vector_results = self.embedding_service.search(
            query=query,
            project_ids=project_ids,
            content_types=content_types,
            top_k=top_k,
        )
        results.extend(vector_results)

        # 2. Direct API queries for specific items or fresh data
        if filters.get("needs_api_query") and project_ids:
            api_results = await self._query_gitlab_api(filters, project_ids)
            results.extend(api_results)

        # 3. Deduplicate and rank
        ranked_results = self._rank_and_dedupe(results, query)

        return ranked_results[:top_k]

    async def _query_gitlab_api(
        self, filters: Dict[str, Any], project_ids: List[int]
    ) -> List[Dict[str, Any]]:
        """Query GitLab API for fresh data."""
        results = []

        for project_id in project_ids[:3]:  # Limit to first 3 projects
            # Fetch specific issue if requested
            if filters.get("issue_iid"):
                try:
                    issue = await self.gitlab_client.get_issue(
                        project_id, filters["issue_iid"]
                    )
                    results.append(self._format_issue_result(issue, project_id))
                except Exception:
                    pass

            # Fetch specific MR if requested
            if filters.get("mr_iid"):
                try:
                    mr = await self.gitlab_client.get_merge_request(
                        project_id, filters["mr_iid"]
                    )
                    results.append(self._format_mr_result(mr, project_id))
                except Exception:
                    pass

            # Search issues with labels
            if filters.get("labels") and "issue" in filters.get("content_types", ["issue"]):
                try:
                    issues = await self.gitlab_client.get_issues(
                        project_id,
                        labels=filters["labels"],
                        state=filters.get("state", "all"),
                    )
                    for issue in issues[:5]:  # Limit results
                        results.append(self._format_issue_result(issue, project_id))
                except Exception:
                    pass

        return results

    def _format_issue_result(self, issue: Dict, project_id: int) -> Dict[str, Any]:
        """Format issue data as retrieval result."""
        content = f"Issue #{issue['iid']}: {issue['title']}\n\n"
        if issue.get("description"):
            content += issue["description"]

        return {
            "id": f"api_issue_{project_id}_{issue['id']}",
            "score": 1.0,  # API results get high relevance
            "content": content,
            "metadata": {
                "type": "issue",
                "project_id": project_id,
                "issue_id": issue["id"],
                "issue_iid": issue["iid"],
                "title": issue["title"],
                "state": issue["state"],
                "labels": issue.get("labels", []),
                "web_url": issue["web_url"],
                "source": "api",
            },
        }

    def _format_mr_result(self, mr: Dict, project_id: int) -> Dict[str, Any]:
        """Format MR data as retrieval result."""
        content = f"Merge Request !{mr['iid']}: {mr['title']}\n\n"
        if mr.get("description"):
            content += mr["description"]

        return {
            "id": f"api_mr_{project_id}_{mr['id']}",
            "score": 1.0,
            "content": content,
            "metadata": {
                "type": "merge_request",
                "project_id": project_id,
                "mr_id": mr["id"],
                "mr_iid": mr["iid"],
                "title": mr["title"],
                "state": mr["state"],
                "labels": mr.get("labels", []),
                "web_url": mr["web_url"],
                "source": "api",
            },
        }

    def _rank_and_dedupe(
        self, results: List[Dict[str, Any]], query: str
    ) -> List[Dict[str, Any]]:
        """Deduplicate and rank results."""
        seen_ids = set()
        unique_results = []

        # Sort by score descending
        sorted_results = sorted(results, key=lambda x: x.get("score", 0), reverse=True)

        for result in sorted_results:
            # Create dedup key based on content type and ID
            meta = result.get("metadata", {})
            dedup_key = None

            if meta.get("type") == "issue":
                dedup_key = f"issue_{meta.get('project_id')}_{meta.get('issue_iid')}"
            elif meta.get("type") == "merge_request":
                dedup_key = f"mr_{meta.get('project_id')}_{meta.get('mr_iid')}"
            elif meta.get("type") == "code":
                dedup_key = f"code_{meta.get('project_id')}_{meta.get('file_path')}_{meta.get('start_line', 0)}"
            elif meta.get("type") == "comment":
                dedup_key = f"comment_{meta.get('comment_id')}"
            else:
                dedup_key = result.get("id", str(len(unique_results)))

            if dedup_key not in seen_ids:
                seen_ids.add(dedup_key)
                unique_results.append(result)

        return unique_results
