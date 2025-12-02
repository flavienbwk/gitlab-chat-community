"""Content chunking strategies for RAG."""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import tiktoken

from config import get_settings


@dataclass
class Chunk:
    """Represents a text chunk with metadata."""

    content: str
    metadata: Dict[str, Any]
    token_count: int = 0


class ChunkingStrategy:
    """Content-aware chunking for different document types."""

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ):
        settings = get_settings()
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.tokenizer.encode(text))

    def _get_overlap_text(self, text: str) -> str:
        """Get overlap text from end of chunk."""
        if not text:
            return ""
        tokens = self.tokenizer.encode(text)
        overlap_tokens = tokens[-self.chunk_overlap :] if len(tokens) > self.chunk_overlap else tokens
        return self.tokenizer.decode(overlap_tokens)

    def _split_large_text(self, text: str, base_metadata: Dict) -> List[Chunk]:
        """Split text larger than chunk_size into multiple chunks."""
        tokens = self.tokenizer.encode(text)
        chunks = []

        start = 0
        while start < len(tokens):
            end = min(start + self.chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = self.tokenizer.decode(chunk_tokens)

            chunks.append(
                Chunk(
                    content=chunk_text,
                    metadata=base_metadata.copy(),
                    token_count=len(chunk_tokens),
                )
            )

            # Move start with overlap
            start = end - self.chunk_overlap if end < len(tokens) else end

        return chunks

    def _semantic_chunk(self, text: str, base_metadata: Dict) -> List[Chunk]:
        """Split text into semantic chunks respecting paragraph boundaries."""
        if not text or not text.strip():
            return []

        # Split by double newlines (paragraphs)
        paragraphs = re.split(r"\n\s*\n", text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        chunks = []
        current_chunk = ""
        current_tokens = 0

        for para in paragraphs:
            para_tokens = self._count_tokens(para)

            # If single paragraph exceeds chunk size, split it
            if para_tokens > self.chunk_size:
                # First, save current chunk if any
                if current_chunk:
                    chunks.append(
                        Chunk(
                            content=current_chunk.strip(),
                            metadata=base_metadata.copy(),
                            token_count=current_tokens,
                        )
                    )
                    current_chunk = ""
                    current_tokens = 0

                # Split large paragraph
                sub_chunks = self._split_large_text(para, base_metadata)
                chunks.extend(sub_chunks)
                continue

            # Check if adding paragraph exceeds chunk size
            if current_tokens + para_tokens > self.chunk_size:
                # Save current chunk
                if current_chunk:
                    chunks.append(
                        Chunk(
                            content=current_chunk.strip(),
                            metadata=base_metadata.copy(),
                            token_count=current_tokens,
                        )
                    )

                # Start new chunk with overlap
                overlap_text = self._get_overlap_text(current_chunk)
                current_chunk = overlap_text + "\n\n" + para if overlap_text else para
                current_tokens = self._count_tokens(current_chunk)
            else:
                # Add to current chunk
                current_chunk = current_chunk + "\n\n" + para if current_chunk else para
                current_tokens += para_tokens

        # Don't forget the last chunk
        if current_chunk.strip():
            chunks.append(
                Chunk(
                    content=current_chunk.strip(),
                    metadata=base_metadata.copy(),
                    token_count=self._count_tokens(current_chunk),
                )
            )

        return chunks

    def chunk_issue(self, issue: Dict, project_id: int) -> List[Chunk]:
        """Chunk an issue with semantic boundaries."""
        chunks = []

        # Chunk 1: Title + metadata (always keep together)
        title_content = f"Issue #{issue['iid']}: {issue['title']}\n\n"
        title_content += f"State: {issue['state']}\n"
        title_content += f"Author: {issue['author']['username']}\n"
        if issue.get("labels"):
            title_content += f"Labels: {', '.join(issue['labels'])}\n"
        if issue.get("milestone"):
            title_content += f"Milestone: {issue['milestone']['title']}\n"
        title_content += f"Created: {issue['created_at']}\n"
        if issue.get("closed_at"):
            title_content += f"Closed: {issue['closed_at']}\n"
        title_content += f"URL: {issue['web_url']}"

        chunks.append(
            Chunk(
                content=title_content,
                metadata={
                    "type": "issue",
                    "subtype": "metadata",
                    "project_id": project_id,
                    "issue_id": issue["id"],
                    "issue_iid": issue["iid"],
                    "title": issue["title"],
                    "state": issue["state"],
                    "labels": issue.get("labels", []),
                    "created_at": issue["created_at"],
                    "web_url": issue["web_url"],
                },
                token_count=self._count_tokens(title_content),
            )
        )

        # Chunk 2+: Description with semantic splitting
        if issue.get("description"):
            desc_chunks = self._semantic_chunk(
                issue["description"],
                {
                    "type": "issue",
                    "subtype": "description",
                    "project_id": project_id,
                    "issue_id": issue["id"],
                    "issue_iid": issue["iid"],
                    "title": issue["title"],
                    "web_url": issue["web_url"],
                },
            )
            chunks.extend(desc_chunks)

        return chunks

    def chunk_comment(
        self, comment: Dict, parent_type: str, parent_iid: int, project_id: int
    ) -> List[Chunk]:
        """Chunk a comment with parent context."""
        # Skip system-generated comments
        if comment.get("system", False):
            return []

        if not comment.get("body") or not comment["body"].strip():
            return []

        metadata = {
            "type": "comment",
            "parent_type": parent_type,
            "parent_iid": parent_iid,
            "project_id": project_id,
            "comment_id": comment["id"],
            "author": comment["author"]["username"],
            "created_at": comment["created_at"],
        }

        return self._semantic_chunk(comment["body"], metadata)

    def chunk_merge_request(self, mr: Dict, project_id: int) -> List[Chunk]:
        """Chunk a merge request with semantic boundaries."""
        chunks = []

        # Chunk 1: Title + metadata
        title_content = f"Merge Request !{mr['iid']}: {mr['title']}\n\n"
        title_content += f"State: {mr['state']}\n"
        title_content += f"Author: {mr['author']['username']}\n"
        title_content += f"Source: {mr['source_branch']} -> {mr['target_branch']}\n"
        if mr.get("labels"):
            title_content += f"Labels: {', '.join(mr['labels'])}\n"
        title_content += f"Created: {mr['created_at']}\n"
        if mr.get("merged_at"):
            title_content += f"Merged: {mr['merged_at']}\n"
        title_content += f"URL: {mr['web_url']}"

        chunks.append(
            Chunk(
                content=title_content,
                metadata={
                    "type": "merge_request",
                    "subtype": "metadata",
                    "project_id": project_id,
                    "mr_id": mr["id"],
                    "mr_iid": mr["iid"],
                    "title": mr["title"],
                    "state": mr["state"],
                    "labels": mr.get("labels", []),
                    "source_branch": mr["source_branch"],
                    "target_branch": mr["target_branch"],
                    "created_at": mr["created_at"],
                    "web_url": mr["web_url"],
                },
                token_count=self._count_tokens(title_content),
            )
        )

        # Chunk 2+: Description
        if mr.get("description"):
            desc_chunks = self._semantic_chunk(
                mr["description"],
                {
                    "type": "merge_request",
                    "subtype": "description",
                    "project_id": project_id,
                    "mr_id": mr["id"],
                    "mr_iid": mr["iid"],
                    "title": mr["title"],
                    "web_url": mr["web_url"],
                },
            )
            chunks.extend(desc_chunks)

        return chunks

    def chunk_code_file(
        self, file_path: str, content: str, project_id: int
    ) -> List[Chunk]:
        """Chunk code files with syntax-aware boundaries."""
        if not content or not content.strip():
            return []

        language = self._detect_language(file_path)
        base_metadata = {
            "type": "code",
            "project_id": project_id,
            "file_path": file_path,
            "language": language,
        }

        # For supported languages, try to chunk by functions/classes
        if language in ["python", "javascript", "typescript"]:
            chunks = self._chunk_by_syntax(content, language, base_metadata)
            if chunks:
                return chunks

        # Fallback: chunk by lines
        return self._chunk_by_lines(content, base_metadata)

    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".rb": "ruby",
            ".php": "php",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".cs": "csharp",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".vue": "vue",
            ".svelte": "svelte",
            ".md": "markdown",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".xml": "xml",
            ".html": "html",
            ".css": "css",
            ".scss": "scss",
            ".sql": "sql",
            ".sh": "bash",
            ".bash": "bash",
            ".zsh": "zsh",
        }

        for ext, lang in ext_map.items():
            if file_path.lower().endswith(ext):
                return lang
        return "unknown"

    def _chunk_by_syntax(
        self, content: str, language: str, base_metadata: Dict
    ) -> List[Chunk]:
        """Chunk code by syntax elements (functions, classes)."""
        chunks = []
        lines = content.split("\n")

        # Simple pattern matching for function/class definitions
        if language == "python":
            patterns = [
                (r"^(class\s+\w+)", "class"),
                (r"^(def\s+\w+)", "function"),
                (r"^(async\s+def\s+\w+)", "async_function"),
            ]
        elif language in ["javascript", "typescript"]:
            patterns = [
                (r"^(class\s+\w+)", "class"),
                (r"^(function\s+\w+)", "function"),
                (r"^(const\s+\w+\s*=\s*(?:async\s*)?\()", "arrow_function"),
                (r"^(export\s+(?:default\s+)?(?:async\s+)?function)", "function"),
            ]
        else:
            return []

        current_block = []
        current_type = "module"
        block_start_line = 0

        for i, line in enumerate(lines):
            # Check if line starts a new block
            new_block = False
            for pattern, block_type in patterns:
                if re.match(pattern, line.strip()):
                    # Save previous block
                    if current_block:
                        block_content = "\n".join(current_block)
                        if block_content.strip():
                            meta = base_metadata.copy()
                            meta["block_type"] = current_type
                            meta["start_line"] = block_start_line + 1
                            meta["end_line"] = i

                            block_chunks = self._semantic_chunk(block_content, meta)
                            chunks.extend(block_chunks)

                    current_block = [line]
                    current_type = block_type
                    block_start_line = i
                    new_block = True
                    break

            if not new_block:
                current_block.append(line)

        # Don't forget the last block
        if current_block:
            block_content = "\n".join(current_block)
            if block_content.strip():
                meta = base_metadata.copy()
                meta["block_type"] = current_type
                meta["start_line"] = block_start_line + 1
                meta["end_line"] = len(lines)

                block_chunks = self._semantic_chunk(block_content, meta)
                chunks.extend(block_chunks)

        return chunks

    def chunk_readme(
        self, content: str, project_id: int, project_name: str, web_url: str
    ) -> List[Chunk]:
        """Chunk README.md content with project context."""
        if not content or not content.strip():
            return []

        # Add a header chunk with project context
        header_content = f"# Project README: {project_name}\n\n"
        header_content += f"URL: {web_url}\n\n"
        header_content += "---\n\n"

        base_metadata = {
            "type": "readme",
            "project_id": project_id,
            "project_name": project_name,
            "web_url": web_url,
            "file_path": "README.md",
        }

        # Use semantic chunking for markdown content
        chunks = self._semantic_chunk(header_content + content, base_metadata)

        return chunks

    def _chunk_by_lines(self, content: str, base_metadata: Dict) -> List[Chunk]:
        """Chunk code by line groups."""
        lines = content.split("\n")
        chunks = []

        current_chunk_lines = []
        current_tokens = 0
        start_line = 0

        for i, line in enumerate(lines):
            line_tokens = self._count_tokens(line + "\n")

            if current_tokens + line_tokens > self.chunk_size and current_chunk_lines:
                # Save current chunk
                chunk_content = "\n".join(current_chunk_lines)
                meta = base_metadata.copy()
                meta["start_line"] = start_line + 1
                meta["end_line"] = i

                chunks.append(
                    Chunk(
                        content=chunk_content,
                        metadata=meta,
                        token_count=current_tokens,
                    )
                )

                # Start new chunk with overlap
                overlap_lines = current_chunk_lines[-5:] if len(current_chunk_lines) > 5 else []
                current_chunk_lines = overlap_lines + [line]
                current_tokens = self._count_tokens("\n".join(current_chunk_lines))
                start_line = i - len(overlap_lines)
            else:
                current_chunk_lines.append(line)
                current_tokens += line_tokens

        # Save last chunk
        if current_chunk_lines:
            chunk_content = "\n".join(current_chunk_lines)
            meta = base_metadata.copy()
            meta["start_line"] = start_line + 1
            meta["end_line"] = len(lines)

            chunks.append(
                Chunk(
                    content=chunk_content,
                    metadata=meta,
                    token_count=self._count_tokens(chunk_content),
                )
            )

        return chunks
