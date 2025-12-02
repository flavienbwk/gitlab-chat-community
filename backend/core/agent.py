"""Chat agent with RAG and streaming support."""

import json
from typing import Any, AsyncGenerator, Dict, List, Optional

import anthropic
from openai import OpenAI

from config import get_settings
from core.code_analysis import CodeAnalysisAgent
from core.retrieval import HybridRetriever


class ChatAgent:
    """Agent for handling chat queries with RAG."""

    SYSTEM_PROMPT = """You are a helpful assistant that answers questions about GitLab projects. You have access to indexed data from issues, merge requests, code, and comments.

When answering:
1. Be specific and cite your sources (issue numbers, MR numbers, file paths)
2. If information comes from multiple sources, synthesize it clearly
3. If you're not sure about something, say so
4. For code questions, include relevant code snippets when helpful
5. Provide links when available (web_url fields)

IMPORTANT: Always format your responses using Markdown syntax (not HTML). Use:
- **bold** for emphasis
- `backticks` for inline code
- ```language for code blocks
- [text](url) for links
- - or * for bullet lists
- 1. 2. 3. for numbered lists

Context will be provided from the search results. Use this context to answer the user's question accurately."""

    def __init__(
        self,
        provider_type: str = "openai",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """Initialize ChatAgent with provider configuration.

        Args:
            provider_type: Type of provider (openai, anthropic, custom)
            api_key: API key for the provider
            base_url: Base URL for API (custom providers or OpenAI-compatible)
            model: Model ID to use
        """
        settings = get_settings()

        self.provider_type = provider_type
        self.model = model or settings.openai_model

        if provider_type == "anthropic":
            self.client = anthropic.Anthropic(api_key=api_key or settings.openai_api_key)
        else:
            # OpenAI or custom (OpenAI-compatible)
            effective_base_url = base_url if base_url else (settings.openai_base_url if settings.openai_base_url else None)
            self.client = OpenAI(
                api_key=api_key or settings.openai_api_key,
                base_url=effective_base_url,
            )

        self.retriever = HybridRetriever()
        self.code_agent = CodeAnalysisAgent()

    def _format_context(self, results: List[Dict[str, Any]]) -> str:
        """Format retrieval results as context for the LLM."""
        if not results:
            return "No relevant context found."

        context_parts = []

        for i, result in enumerate(results, 1):
            meta = result.get("metadata", {})
            content = result.get("content", "")
            score = result.get("score", 0)

            # Format based on content type
            if meta.get("type") == "issue":
                header = f"[Issue #{meta.get('issue_iid', '?')}] {meta.get('title', 'Untitled')}"
                if meta.get("web_url"):
                    header += f"\nURL: {meta['web_url']}"
            elif meta.get("type") == "merge_request":
                header = f"[MR !{meta.get('mr_iid', '?')}] {meta.get('title', 'Untitled')}"
                if meta.get("web_url"):
                    header += f"\nURL: {meta['web_url']}"
            elif meta.get("type") == "code":
                file_path = meta.get("file_path", "unknown")
                start_line = meta.get("start_line", "")
                end_line = meta.get("end_line", "")
                header = f"[Code] {file_path}"
                if start_line:
                    header += f" (lines {start_line}-{end_line})"
            elif meta.get("type") == "comment":
                parent_type = meta.get("parent_type", "")
                parent_iid = meta.get("parent_iid", "")
                author = meta.get("author", "unknown")
                header = f"[Comment by {author}] on {parent_type} #{parent_iid}"
            else:
                header = f"[Result {i}]"

            context_parts.append(f"---\n{header}\n\n{content}\n")

        return "\n".join(context_parts)

    async def _is_code_query(self, query: str) -> bool:
        """Determine if query is about code analysis."""
        code_keywords = [
            "code",
            "function",
            "class",
            "method",
            "implementation",
            "file",
            "module",
            "import",
            "api",
            "endpoint",
            "handler",
            "component",
            "hook",
            "variable",
            "constant",
        ]
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in code_keywords)

    async def chat(
        self,
        query: str,
        conversation_history: List[Dict[str, str]],
        project_ids: Optional[List[int]] = None,
    ) -> str:
        """Process a chat query and return response."""
        # Retrieve relevant context
        retrieval_results = await self.retriever.retrieve(
            query=query,
            project_ids=project_ids,
        )

        # Check if this is a code-specific query
        code_analysis = None
        if await self._is_code_query(query) and project_ids:
            for project_id in project_ids[:1]:  # Analyze first project
                code_analysis = await self.code_agent.analyze(query, project_id)
                break

        # Build context
        context = self._format_context(retrieval_results)

        if code_analysis and code_analysis.get("answer"):
            context += f"\n\n---\n[Code Analysis]\n{code_analysis['answer']}"

        # Build messages
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
        ]

        # Add conversation history
        for msg in conversation_history[-10:]:  # Keep last 10 messages
            messages.append({"role": msg["role"], "content": msg["content"]})

        # Add context and query
        user_message = f"Context:\n{context}\n\n---\nUser Question: {query}"
        messages.append({"role": "user", "content": user_message})

        # Get response based on provider type
        if self.provider_type == "anthropic":
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=self.SYSTEM_PROMPT,
                messages=[m for m in messages if m["role"] != "system"],
            )
            return response.content[0].text if response.content else "I couldn't generate a response."
        else:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
            )
            return response.choices[0].message.content or "I couldn't generate a response."

    async def chat_stream(
        self,
        query: str,
        conversation_history: List[Dict[str, str]],
        project_ids: Optional[List[int]] = None,
    ) -> AsyncGenerator[str, None]:
        """Process a chat query and stream the response."""
        # Retrieve relevant context
        retrieval_results = await self.retriever.retrieve(
            query=query,
            project_ids=project_ids,
        )

        # Check if this is a code-specific query
        code_analysis = None
        if await self._is_code_query(query) and project_ids:
            for project_id in project_ids[:1]:
                code_analysis = await self.code_agent.analyze(query, project_id)
                break

        # Build context
        context = self._format_context(retrieval_results)

        if code_analysis and code_analysis.get("answer"):
            context += f"\n\n---\n[Code Analysis]\n{code_analysis['answer']}"

        # Build messages
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
        ]

        # Add conversation history
        for msg in conversation_history[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # Add context and query
        user_message = f"Context:\n{context}\n\n---\nUser Question: {query}"
        messages.append({"role": "user", "content": user_message})

        # Stream response based on provider type
        if self.provider_type == "anthropic":
            with self.client.messages.stream(
                model=self.model,
                max_tokens=2000,
                system=self.SYSTEM_PROMPT,
                messages=[m for m in messages if m["role"] != "system"],
            ) as stream:
                for text in stream.text_stream:
                    yield text
        else:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
                stream=True,
            )

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

    async def generate_title(self, first_message: str) -> str:
        """Generate a title for a conversation based on the first message."""
        if self.provider_type == "anthropic":
            response = self.client.messages.create(
                model=self.model,
                max_tokens=50,
                system="Generate a short, descriptive title (max 50 chars) for a conversation that starts with the following message. Return only the title, no quotes or punctuation.",
                messages=[{"role": "user", "content": first_message}],
            )
            title = response.content[0].text if response.content else "New Conversation"
        else:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Generate a short, descriptive title (max 50 chars) for a conversation that starts with the following message. Return only the title, no quotes or punctuation.",
                    },
                    {"role": "user", "content": first_message},
                ],
                temperature=0.7,
                max_tokens=50,
            )
            title = response.choices[0].message.content or "New Conversation"

        return title[:50]  # Ensure max length
