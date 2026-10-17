from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.chatbot import ChatbotOrchestrator
from app.conversation_store import ConversationNotFoundError, ConversationStore
from app.dependencies import get_chatbot_orchestrator, get_conversation_store
from app.models import Conversation, ConversationMessage


router = APIRouter(prefix="/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: str | None = None
    history: list[dict[str, str]] | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    tool_calls: list[str] = Field(default_factory=list)


class ConversationHistoryResponse(BaseModel):
    conversation: Conversation
    messages: list[ConversationMessage]


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    orchestrator: ChatbotOrchestrator = Depends(get_chatbot_orchestrator),
) -> ChatResponse:
    try:
        result = orchestrator.chat(
            payload.message,
            conversation_id=payload.conversation_id,
            history=payload.history,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ChatResponse(
        conversation_id=result.conversation_id,
        answer=result.answer,
        tool_calls=result.tool_calls,
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
