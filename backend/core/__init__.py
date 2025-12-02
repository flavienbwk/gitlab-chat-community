"""Core modules for GitLab Chat."""

from core.agent import ChatAgent
from core.chunking import ChunkingStrategy
from core.code_analysis import CodeAnalysisAgent
from core.embedding import EmbeddingService
from core.gitlab_client import GitLabClient
from core.retrieval import HybridRetriever

__all__ = [
    "GitLabClient",
    "ChunkingStrategy",
    "EmbeddingService",
    "HybridRetriever",
    "CodeAnalysisAgent",
    "ChatAgent",
]
