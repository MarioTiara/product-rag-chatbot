from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.chatbot import ChatbotOrchestrator
from app.dependencies import get_chatbot_orchestrator


router = APIRouter(prefix="/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    history: list[dict[str, str]] | None = None


class ChatResponse(BaseModel):
    answer: str
    tool_calls: list[str] = Field(default_factory=list)


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    orchestrator: ChatbotOrchestrator = Depends(get_chatbot_orchestrator),
) -> ChatResponse:
    try:
        result = orchestrator.chat(payload.message, payload.history)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ChatResponse(answer=result.answer, tool_calls=result.tool_calls)
