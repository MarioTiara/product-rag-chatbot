from __future__ import annotations

import logging
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.agents.chatbot_orchestrator import ChatbotOrchestrator
from app.agents.utils.exceptions import     ChatProviderAuthenticationError

from app.exceptions.exception import ConversationNotFoundError
from app.api.dependencies import (
    get_chatbot_orchestrator,
    get_conversation_service,
    get_current_user,
)
from app.schemes.chat import ChatRequest, ChatResponse
from app.schemes.conversation import ConversationHistoryResponse
from app.services.conversation_service import ConversationService



logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
    dependencies=[Depends(get_current_user)],
)


def _get_user_id(current_user: Any) -> str:
    """Extract the authenticated user's ID from the dependency result."""
    user_id = (
        current_user.get("id")
        if isinstance(current_user, dict)
        else getattr(current_user, "id", None)
    )

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Authenticated user ID is missing",
        )

    return str(user_id)


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    current_user: Any = Depends(get_current_user),
    orchestrator: ChatbotOrchestrator = Depends(get_chatbot_orchestrator),
) -> ChatResponse:
    request_id = str(uuid.uuid4())
    user_id = _get_user_id(current_user)
    channel = payload.channel or "web"

    try:
        logger.info(
            "Incoming chat request | request_id=%s | conversation_id=%s | user_id=%s | channel=%s | channel_chat_id=%s | channel_thread_id=%s | channel_user_id=%s | channel_message_id=%s | message=%r",
            request_id,
            payload.conversation_id,
            user_id,
            channel,
            payload.channel_chat_id,
            payload.channel_thread_id,
            payload.channel_user_id,
            payload.channel_message_id,
            " ".join(payload.message.split()),
        )

        result = orchestrator.chat(
            message=payload.message,
            conversation_id=payload.conversation_id,
            user_id=user_id,
            channel=payload.channel,
            channel_chat_id=payload.channel_chat_id,
            channel_thread_id=payload.channel_thread_id,
            channel_user_id=payload.channel_user_id,
            channel_message_id=payload.channel_message_id,
            request_id=request_id
        )

    except ConversationNotFoundError as exc:
        logger.warning(
            "Conversation not found | request_id=%s | user_id=%s | conversation_id=%s | error=%s",
            request_id,
            user_id,
            payload.conversation_id,
            exc,
        )
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        ) from exc

    except HTTPException:
        raise

    except ValueError as exc:
        logger.warning(
            "Invalid chat request | request_id=%s | user_id=%s | channel=%s | error=%s",
            request_id,
            user_id,
            channel,
            exc,
        )
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except ChatProviderAuthenticationError as exc:
        logger.warning(
            "Chat provider authentication failed | request_id=%s | user_id=%s | error=%s",
            request_id,
            user_id,
            exc,
        )
        raise HTTPException(
            status_code=503,
            detail="AI provider authentication failed. Please check OPENAI_API_KEY.",
        ) from exc

    except Exception:
        logger.exception(
            "Unexpected error while processing chat request | request_id=%s | user_id=%s | conversation_id=%s",
            request_id,
            user_id,
            payload.conversation_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        ) from None

    logger.info(
        "Chat request completed | request_id=%s | conversation_id=%s | user_id=%s | channel=%s | assistant_message_id=%s",
        request_id,
        result.conversation_id,
        user_id,
        channel,
        result.assistant_message_id,
    )

    return ChatResponse(
        conversation_id=result.conversation_id,
        answer=result.answer,
        assistant_message_id=result.assistant_message_id,
        channel_conversation_id=result.channel_conversation_id,
    )

@router.get(
    "/{conversation_id}/history",
    response_model=ConversationHistoryResponse,
)
def get_conversation_history(
    conversation_id: str,
    current_user: Any = Depends(get_current_user),
    conversation_service: ConversationService = Depends(
        get_conversation_service
    ),
) -> ConversationHistoryResponse:
    user_id = _get_user_id(current_user)

    try:
        # The service/repository must verify ownership before returning history.
        conversation = conversation_service.conversations.get_conversation(
            conversation_id
        )

        if conversation is None:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found",
            )

        conversation_user_id = (
            conversation.get("user_id")
            if isinstance(conversation, dict)
            else getattr(conversation, "user_id", None)
        )

        if conversation_user_id != user_id:
            # Do not reveal whether another user's conversation exists.
            raise HTTPException(
                status_code=404,
                detail="Conversation not found",
            )

        messages = conversation_service.conversations.get_history(
            conversation_id=conversation_id,
            limit=100,
        )

    except HTTPException:
        raise

    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        ) from exc

    return ConversationHistoryResponse(
        conversation=conversation,
        messages=messages,
    )
