"""Data access layer - repository pattern."""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Conversation, IndexedItem, LLMProvider, Message, Project


class ProjectRepository:
    """Repository for Project operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> List[Project]:
        """Get all projects."""
        result = await self.session.execute(select(Project).order_by(Project.name))
        return list(result.scalars().all())

    async def get_by_id(self, project_id: int) -> Optional[Project]:
        """Get project by ID."""
        result = await self.session.execute(
            select(Project).where(Project.id == project_id)
        )
        return result.scalar_one_or_none()

    async def get_by_gitlab_id(self, gitlab_id: int) -> Optional[Project]:
        """Get project by GitLab ID."""
        result = await self.session.execute(
            select(Project).where(Project.gitlab_id == gitlab_id)
        )
        return result.scalar_one_or_none()

    async def get_selected(self) -> List[Project]:
        """Get selected projects for querying."""
        result = await self.session.execute(
            select(Project).where(Project.is_selected == True).order_by(Project.name)
        )
        return list(result.scalars().all())

    async def create(self, **kwargs) -> Project:
        """Create a new project."""
        project = Project(**kwargs)
        self.session.add(project)
        await self.session.flush()
        return project

    async def upsert(self, gitlab_id: int, **kwargs) -> Project:
        """Create or update project by GitLab ID."""
        project = await self.get_by_gitlab_id(gitlab_id)
        if project:
            for key, value in kwargs.items():
                setattr(project, key, value)
            await self.session.flush()
        else:
            project = await self.create(gitlab_id=gitlab_id, **kwargs)
        return project

    async def update_status(
        self,
        project_id: int,
        status: str,
        error: Optional[str] = None,
    ) -> None:
        """Update project indexing status."""
        values = {"indexing_status": status, "indexing_error": error}
        if status == "completed":
            values["is_indexed"] = True
            values["last_indexed_at"] = datetime.utcnow()
        await self.session.execute(
            update(Project).where(Project.id == project_id).values(**values)
        )
        await self.session.flush()

    async def set_selected(self, project_id: int, selected: bool) -> None:
        """Set project selection status."""
        await self.session.execute(
            update(Project).where(Project.id == project_id).values(is_selected=selected)
        )
        await self.session.flush()


class ConversationRepository:
    """Repository for Conversation operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> List[Conversation]:
        """Get all conversations ordered by most recent."""
        result = await self.session.execute(
            select(Conversation).order_by(Conversation.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, conversation_id: uuid.UUID) -> Optional[Conversation]:
        """Get conversation by ID with messages."""
        result = await self.session.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def create(self, title: Optional[str] = None) -> Conversation:
        """Create a new conversation."""
        conversation = Conversation(title=title)
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def update_title(self, conversation_id: uuid.UUID, title: str) -> None:
        """Update conversation title."""
        await self.session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(title=title, updated_at=datetime.utcnow())
        )
        await self.session.flush()

    async def delete(self, conversation_id: uuid.UUID) -> None:
        """Delete a conversation."""
        await self.session.execute(
            delete(Conversation).where(Conversation.id == conversation_id)
        )
        await self.session.flush()

    async def delete_all(self) -> None:
        """Delete all conversations."""
        await self.session.execute(delete(Conversation))
        await self.session.flush()


class MessageRepository:
    """Repository for Message operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_conversation(self, conversation_id: uuid.UUID) -> List[Message]:
        """Get all messages for a conversation."""
        result = await self.session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        return list(result.scalars().all())

    async def create(
        self,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        extra_data: Optional[dict] = None,
    ) -> Message:
        """Create a new message."""
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            extra_data=extra_data or {},
        )
        self.session.add(message)
        await self.session.flush()

        # Update conversation timestamp
        await self.session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=datetime.utcnow())
        )

        return message


class IndexedItemRepository:
    """Repository for IndexedItem operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_project(self, project_id: int) -> List[IndexedItem]:
        """Get all indexed items for a project."""
        result = await self.session.execute(
            select(IndexedItem).where(IndexedItem.project_id == project_id)
        )
        return list(result.scalars().all())

    async def get_by_item(
        self, project_id: int, item_type: str, item_id: int
    ) -> Optional[IndexedItem]:
        """Get indexed item by project, type, and item ID."""
        result = await self.session.execute(
            select(IndexedItem).where(
                IndexedItem.project_id == project_id,
                IndexedItem.item_type == item_type,
                IndexedItem.item_id == item_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        project_id: int,
        item_type: str,
        item_id: int,
        item_iid: Optional[int] = None,
        qdrant_point_ids: Optional[List[str]] = None,
        last_updated_at: Optional[datetime] = None,
    ) -> IndexedItem:
        """Create or update indexed item."""
        item = await self.get_by_item(project_id, item_type, item_id)
        if item:
            item.qdrant_point_ids = qdrant_point_ids or []
            item.last_updated_at = last_updated_at
            item.indexed_at = datetime.utcnow()
            await self.session.flush()
        else:
            item = IndexedItem(
                project_id=project_id,
                item_type=item_type,
                item_id=item_id,
                item_iid=item_iid,
                qdrant_point_ids=qdrant_point_ids or [],
                last_updated_at=last_updated_at,
            )
            self.session.add(item)
            await self.session.flush()
        return item

    async def delete_by_project(self, project_id: int) -> None:
        """Delete all indexed items for a project."""
        await self.session.execute(
            delete(IndexedItem).where(IndexedItem.project_id == project_id)
        )
        await self.session.flush()


class LLMProviderRepository:
    """Repository for LLMProvider operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> List[LLMProvider]:
        """Get all LLM providers."""
        result = await self.session.execute(
            select(LLMProvider).order_by(LLMProvider.name)
        )
        return list(result.scalars().all())

    async def get_by_id(self, provider_id: int) -> Optional[LLMProvider]:
        """Get provider by ID."""
        result = await self.session.execute(
            select(LLMProvider).where(LLMProvider.id == provider_id)
        )
        return result.scalar_one_or_none()

    async def get_default(self) -> Optional[LLMProvider]:
        """Get the default provider."""
        result = await self.session.execute(
            select(LLMProvider).where(LLMProvider.is_default == True)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        name: str,
        provider_type: str,
        api_key: str,
        model_id: str,
        base_url: Optional[str] = None,
        host_country: Optional[str] = None,
        is_default: bool = False,
    ) -> LLMProvider:
        """Create a new LLM provider."""
        # If this is the first provider or marked as default, ensure it's the only default
        if is_default:
            await self._clear_default()

        provider = LLMProvider(
            name=name,
            provider_type=provider_type,
            api_key=api_key,
            model_id=model_id,
            base_url=base_url,
            host_country=host_country,
            is_default=is_default,
        )
        self.session.add(provider)
        await self.session.flush()
        return provider

    async def update(
        self,
        provider_id: int,
        name: Optional[str] = None,
        provider_type: Optional[str] = None,
        api_key: Optional[str] = None,
        model_id: Optional[str] = None,
        base_url: Optional[str] = None,
        host_country: Optional[str] = None,
        is_default: Optional[bool] = None,
    ) -> Optional[LLMProvider]:
        """Update an existing provider."""
        provider = await self.get_by_id(provider_id)
        if not provider:
            return None

        if name is not None:
            provider.name = name
        if provider_type is not None:
            provider.provider_type = provider_type
        if api_key is not None:
            provider.api_key = api_key
        if model_id is not None:
            provider.model_id = model_id
        if base_url is not None:
            provider.base_url = base_url if base_url else None
        if host_country is not None:
            provider.host_country = host_country if host_country else None
        if is_default is not None:
            if is_default:
                await self._clear_default()
            provider.is_default = is_default

        await self.session.flush()
        return provider

    async def delete(self, provider_id: int) -> bool:
        """Delete a provider."""
        provider = await self.get_by_id(provider_id)
        if not provider:
            return False

        await self.session.execute(
            delete(LLMProvider).where(LLMProvider.id == provider_id)
        )
        await self.session.flush()
        return True

    async def set_default(self, provider_id: int) -> Optional[LLMProvider]:
        """Set a provider as default."""
        provider = await self.get_by_id(provider_id)
        if not provider:
            return None

        await self._clear_default()
        provider.is_default = True
        await self.session.flush()
        return provider

    async def _clear_default(self) -> None:
        """Clear the default flag from all providers."""
        await self.session.execute(
            update(LLMProvider).where(LLMProvider.is_default == True).values(is_default=False)
        )
        await self.session.flush()
