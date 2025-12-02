"""Chat API routes."""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from api.dependencies import (
    get_conversation_repo,
    get_message_repo,
    get_project_repo,
    get_provider_repo,
)
from core.agent import ChatAgent
from db.database import async_session_maker
from db.repositories import ConversationRepository, LLMProviderRepository, MessageRepository, ProjectRepository

router = APIRouter()


class ChatRequest(BaseModel):
    """Chat request model."""

    message: str
    conversation_id: Optional[str] = None
    provider_id: Optional[int] = None  # Optional provider ID, uses default if not specified


class ChatResponse(BaseModel):
    """Chat response model."""

    conversation_id: str
    message: str
    title: Optional[str] = None


async def _get_agent_for_provider(
    provider_id: Optional[int],
    provider_repo: LLMProviderRepository,
) -> ChatAgent:
    """Get a ChatAgent configured for the specified or default provider."""
    provider = None

    if provider_id:
        provider = await provider_repo.get_by_id(provider_id)
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")
    else:
        # Try to get default provider
        provider = await provider_repo.get_default()

    if provider:
        return ChatAgent(
            provider_type=provider.provider_type,
            api_key=provider.api_key,
            base_url=provider.base_url,
            model=provider.model_id,
        )
    else:
        # Fall back to env-based config
        return ChatAgent()


@router.post("/chat")
async def chat(
    request: ChatRequest,
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    message_repo: MessageRepository = Depends(get_message_repo),
    project_repo: ProjectRepository = Depends(get_project_repo),
    provider_repo: LLMProviderRepository = Depends(get_provider_repo),
):
    """Send a chat message and receive a streaming response."""

    # Get agent for provider
    agent = await _get_agent_for_provider(request.provider_id, provider_repo)

    # Get or create conversation
    conversation_id = None
    is_new_conversation = False

    if request.conversation_id:
        try:
            conversation_id = uuid.UUID(request.conversation_id)
            conversation = await conversation_repo.get_by_id(conversation_id)
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid conversation ID")
    else:
        # Create new conversation
        conversation = await conversation_repo.create()
        conversation_id = conversation.id
        is_new_conversation = True

    # Save user message
    await message_repo.create(
        conversation_id=conversation_id,
        role="user",
        content=request.message,
    )

    # Get conversation history
    messages = await message_repo.get_by_conversation(conversation_id)
    history = [{"role": m.role, "content": m.content} for m in messages[:-1]]  # Exclude current message

    # Get selected projects
    selected_projects = await project_repo.get_selected()
    project_ids = [p.gitlab_id for p in selected_projects]

    async def generate():
        """Generate streaming response."""
        full_response = ""
        generated_title = None

        try:
            async for token in agent.chat_stream(
                query=request.message,
                conversation_history=history,
                project_ids=project_ids if project_ids else None,
            ):
                full_response += token
                yield {"event": "message", "data": token}

            # Create a new database session for saving results
            # (the original session from dependency injection is closed by now)
            async with async_session_maker() as session:
                msg_repo = MessageRepository(session)
                conv_repo = ConversationRepository(session)

                # Save assistant response
                await msg_repo.create(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=full_response,
                )

                # Generate title for new conversations
                if is_new_conversation:
                    generated_title = await agent.generate_title(request.message)
                    await conv_repo.update_title(conversation_id, generated_title)

                await session.commit()

            # Yield title and done events outside the async with block
            # to ensure they are properly sent
            if generated_title:
                yield {"event": "title", "data": generated_title}

            yield {"event": "done", "data": str(conversation_id)}

        except Exception as e:
            import traceback
            print(f"Chat error: {e}")
            traceback.print_exc()
            yield {"event": "error", "data": str(e)}

    return EventSourceResponse(generate())


@router.post("/chat/sync", response_model=ChatResponse)
async def chat_sync(
    request: ChatRequest,
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    message_repo: MessageRepository = Depends(get_message_repo),
    project_repo: ProjectRepository = Depends(get_project_repo),
    provider_repo: LLMProviderRepository = Depends(get_provider_repo),
):
    """Send a chat message and receive a non-streaming response."""

    # Get agent for provider
    agent = await _get_agent_for_provider(request.provider_id, provider_repo)

    # Get or create conversation
    conversation_id = None
    is_new_conversation = False

    if request.conversation_id:
        try:
            conversation_id = uuid.UUID(request.conversation_id)
            conversation = await conversation_repo.get_by_id(conversation_id)
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid conversation ID")
    else:
        conversation = await conversation_repo.create()
        conversation_id = conversation.id
        is_new_conversation = True

    # Save user message
    await message_repo.create(
        conversation_id=conversation_id,
        role="user",
        content=request.message,
    )

    # Get conversation history
    messages = await message_repo.get_by_conversation(conversation_id)
    history = [{"role": m.role, "content": m.content} for m in messages[:-1]]

    # Get selected projects
    selected_projects = await project_repo.get_selected()
    project_ids = [p.gitlab_id for p in selected_projects]

    # Get response
    response = await agent.chat(
        query=request.message,
        conversation_history=history,
        project_ids=project_ids if project_ids else None,
    )

    # Save assistant response
    await message_repo.create(
        conversation_id=conversation_id,
        role="assistant",
        content=response,
    )

    # Generate title for new conversations
    title = None
    if is_new_conversation:
        title = await agent.generate_title(request.message)
        await conversation_repo.update_title(conversation_id, title)

    return ChatResponse(
        conversation_id=str(conversation_id),
        message=response,
        title=title,
    )
