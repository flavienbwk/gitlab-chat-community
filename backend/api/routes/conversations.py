"""Conversation API routes."""

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.dependencies import get_conversation_repo, get_message_repo
from db.repositories import ConversationRepository, MessageRepository

router = APIRouter()


class MessageResponse(BaseModel):
    """Message response model."""

    id: str
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    """Conversation response model."""

    id: str
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    class Config:
        from_attributes = True


class ConversationDetailResponse(BaseModel):
    """Conversation detail with messages."""

    id: str
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse]


class ConversationListResponse(BaseModel):
    """Conversation list response."""

    conversations: List[ConversationResponse]
    total: int


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    message_repo: MessageRepository = Depends(get_message_repo),
):
    """List all conversations."""
    conversations = await conversation_repo.get_all()

    response_items = []
    for conv in conversations:
        messages = await message_repo.get_by_conversation(conv.id)
        response_items.append(
            ConversationResponse(
                id=str(conv.id),
                title=conv.title,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                message_count=len(messages),
            )
        )

    return ConversationListResponse(
        conversations=response_items,
        total=len(response_items),
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: str,
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    message_repo: MessageRepository = Depends(get_message_repo),
):
    """Get a specific conversation with messages."""
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")

    conversation = await conversation_repo.get_by_id(conv_uuid)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = await message_repo.get_by_conversation(conv_uuid)

    return ConversationDetailResponse(
        id=str(conversation.id),
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[
            MessageResponse(
                id=str(m.id),
                role=m.role,
                content=m.content,
                created_at=m.created_at,
            )
            for m in messages
        ],
    )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
):
    """Delete a specific conversation."""
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")

    conversation = await conversation_repo.get_by_id(conv_uuid)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await conversation_repo.delete(conv_uuid)

    return {"status": "deleted", "conversation_id": conversation_id}


@router.delete("/conversations")
async def clear_all_conversations(
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
):
    """Delete all conversations."""
    await conversation_repo.delete_all()
    return {"status": "cleared", "message": "All conversations deleted"}


@router.patch("/conversations/{conversation_id}/title")
async def update_conversation_title(
    conversation_id: str,
    title: str,
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
):
    """Update conversation title."""
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")

    conversation = await conversation_repo.get_by_id(conv_uuid)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await conversation_repo.update_title(conv_uuid, title)

    return {"status": "updated", "conversation_id": conversation_id, "title": title}
