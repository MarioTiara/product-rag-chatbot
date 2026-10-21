from __future__ import annotations
import logging

from fastapi import APIRouter, Depends, HTTPException


from app.ai.chatbot_service import ChatbotOrchestrator
from app.api.dependencies import get_chatbot_orchestrator, get_conversation_store, get_current_user
from app.schemes.chat import ChatRequest, ChatResponse
from app.schemes.conversation import ConversationHistoryResponse
from app.services.conversation_store import ConversationNotFoundError, ConversationStore


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/chat", tags=["Chat"], dependencies=[Depends(get_current_user)])

@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    orchestrator: ChatbotOrchestrator = Depends(get_chatbot_orchestrator),
) -> ChatResponse:
    try:
        logger.info("Received chat request")

        result = orchestrator.chat(
            payload.message,
            conversation_id=payload.conversation_id,
        )

    except ConversationNotFoundError as exc:
        logger.warning("Conversation not found: %s", exc)
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        ) from exc

    except ValueError as exc:
        logger.warning("Invalid chat request: %s", exc)
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception:
        logger.exception("Unexpected error while processing chat request")
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        ) from None

    logger.info(
        "Chat request completed successfully: conversation_id=%s",
        result.conversation_id,
    )

    return ChatResponse(
        conversation_id=result.conversation_id,
        answer=result.answer,
    )


@router.get("/{conversation_id}/history", response_model=ConversationHistoryResponse)
def get_conversation_history(
    conversation_id: str,
    store: ConversationStore = Depends(get_conversation_store),
) -> ConversationHistoryResponse:
    try:
        conversation = store.get_conversation(conversation_id)
        messages = store.get_messages(conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found") from exc

    return ConversationHistoryResponse(conversation=conversation, messages=messages)
