
from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.agents.chatbot_orchestrator import ChatbotOrchestrator
from app.agents.utils.exceptions import ChatProviderAuthenticationError
from app.api.dependencies import (
    get_chatbot_orchestrator,
    get_conversation_service,
    get_current_user,
)
from app.core.exceptions.exception import ConversationNotFoundError
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


def _get_request_id(request: Request) -> str:
    """Reuse the request ID assigned by observability middleware."""
    return getattr(request.state, "request_id", None) or str(uuid.uuid4())


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    request: Request,
    current_user: Any = Depends(get_current_user),
    orchestrator: ChatbotOrchestrator = Depends(get_chatbot_orchestrator),
) -> ChatResponse:
    request_id = _get_request_id(request)
    user_id = _get_user_id(current_user)
    channel = payload.channel or "web"

    started_at = time.perf_counter()

    log_context = {
        "request_id": request_id,
        "conversation_id": payload.conversation_id,
        "user_id": user_id,
        "channel": channel,
    }

    logger.info(
        "Incoming chat request",
        extra={
            **log_context,
            "event": "chat_request_started",
        },
    )

    try:
        result = orchestrator.chat(
            message=payload.message,
            conversation_id=payload.conversation_id,
            user_id=user_id,
            channel=payload.channel,
            channel_chat_id=payload.channel_chat_id,
            channel_thread_id=payload.channel_thread_id,
            channel_user_id=payload.channel_user_id,
            channel_message_id=payload.channel_message_id,
            request_id=request_id,
        )

    except ConversationNotFoundError as exc:
        logger.warning(
            "Conversation not found",
            extra={
                **log_context,
                "event": "chat_conversation_not_found",
                "error_type": type(exc).__name__,
                "duration_ms": round(
                    (time.perf_counter() - started_at) * 1000, 2
                ),
            },
        )
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        ) from exc

    except HTTPException:
        raise

    except ValueError as exc:
        logger.warning(
            "Invalid chat request",
            extra={
                **log_context,
                "event": "chat_request_invalid",
                "error_type": type(exc).__name__,
                "duration_ms": round(
                    (time.perf_counter() - started_at) * 1000, 2
                ),
            },
        )
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except ChatProviderAuthenticationError as exc:
        logger.error(
            "Chat provider authentication failed",
            extra={
                **log_context,
                "event": "chat_provider_authentication_failed",
                "error_type": type(exc).__name__,
                "duration_ms": round(
                    (time.perf_counter() - started_at) * 1000, 2
                ),
            },
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "AI provider authentication failed. "
                "Please check OPENAI_API_KEY."
            ),
        ) from exc

    except Exception as exc:
        logger.exception(
            "Unexpected error while processing chat request",
            extra={
                **log_context,
                "event": "chat_request_failed",
                "error_type": type(exc).__name__,
                "duration_ms": round(
                    (time.perf_counter() - started_at) * 1000, 2
                ),
            },
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        ) from None

    duration_ms = round(
        (time.perf_counter() - started_at) * 1000,
        2,
    )

    logger.info(
        "Chat request completed",
        extra={
            **log_context,
            "event": "chat_request_completed",
            "conversation_id": result.conversation_id,
            "assistant_message_id": result.assistant_message_id,
            "duration_ms": duration_ms,
            "status_code": 200,
        },
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
    request: Request,
    current_user: Any = Depends(get_current_user),
    conversation_service: ConversationService = Depends(
        get_conversation_service
    ),
) -> ConversationHistoryResponse:
    request_id = _get_request_id(request)
    user_id = _get_user_id(current_user)
    started_at = time.perf_counter()

    log_context = {
        "request_id": request_id,
        "conversation_id": conversation_id,
        "user_id": user_id,
        "channel": "api",
    }

    logger.info(
        "Conversation history requested",
        extra={
            **log_context,
            "event": "conversation_history_started",
        },
    )

    try:
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

        if str(conversation_user_id) != user_id:
            # Do not disclose whether another user's conversation exists.
            raise HTTPException(
                status_code=404,
                detail="Conversation not found",
            )

        messages = conversation_service.conversations.get_history(
            conversation_id=conversation_id,
            limit=100,
        )

    except HTTPException as exc:
        logger.warning(
            "Conversation history request rejected",
            extra={
                **log_context,
                "event": "conversation_history_rejected",
                "status_code": exc.status_code,
                "duration_ms": round(
                    (time.perf_counter() - started_at) * 1000, 2
                ),
            },
        )
        raise

    except ConversationNotFoundError as exc:
        logger.warning(
            "Conversation history not found",
            extra={
                **log_context,
                "event": "conversation_history_not_found",
                "error_type": type(exc).__name__,
                "duration_ms": round(
                    (time.perf_counter() - started_at) * 1000, 2
                ),
            },
        )
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        ) from exc

    except Exception as exc:
        logger.exception(
            "Unexpected error retrieving conversation history",
            extra={
                **log_context,
                "event": "conversation_history_failed",
                "error_type": type(exc).__name__,
                "duration_ms": round(
                    (time.perf_counter() - started_at) * 1000, 2
                ),
            },
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        ) from None

    logger.info(
        "Conversation history retrieved",
        extra={
            **log_context,
            "event": "conversation_history_completed",
            "message_count": len(messages),
            "duration_ms": round(
                (time.perf_counter() - started_at) * 1000, 2
            ),
            "status_code": 200,
        },
    )

    return ConversationHistoryResponse(
        conversation=conversation,
        messages=messages,
    )
