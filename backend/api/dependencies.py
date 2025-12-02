"""FastAPI dependencies."""

from typing import AsyncGenerator, List, Optional

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.agent import ChatAgent
from core.embedding import EmbeddingService
from core.gitlab_client import GitLabClient
from core.retrieval import HybridRetriever
from db.database import get_db
from db.repositories import (
    ConversationRepository,
    IndexedItemRepository,
    LLMProviderRepository,
    MessageRepository,
    ProjectRepository,
)


async def get_project_repo(
    db: AsyncSession = Depends(get_db),
) -> ProjectRepository:
    """Get project repository."""
    return ProjectRepository(db)


async def get_conversation_repo(
    db: AsyncSession = Depends(get_db),
) -> ConversationRepository:
    """Get conversation repository."""
    return ConversationRepository(db)


async def get_message_repo(
    db: AsyncSession = Depends(get_db),
) -> MessageRepository:
    """Get message repository."""
    return MessageRepository(db)


async def get_indexed_item_repo(
    db: AsyncSession = Depends(get_db),
) -> IndexedItemRepository:
    """Get indexed item repository."""
    return IndexedItemRepository(db)


def get_gitlab_client() -> GitLabClient:
    """Get GitLab client."""
    return GitLabClient()


def get_embedding_service() -> EmbeddingService:
    """Get embedding service."""
    return EmbeddingService()


def get_retriever() -> HybridRetriever:
    """Get hybrid retriever."""
    return HybridRetriever()


def get_chat_agent() -> ChatAgent:
    """Get chat agent."""
    return ChatAgent()


async def get_provider_repo(
    db: AsyncSession = Depends(get_db),
) -> LLMProviderRepository:
    """Get LLM provider repository."""
    return LLMProviderRepository(db)
