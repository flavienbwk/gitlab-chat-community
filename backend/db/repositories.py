"""Data access layer - repository pattern."""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Conversation, IndexedItem, Message, Project


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
