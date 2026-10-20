
from __future__ import annotations

from typing import Any
from typing import Literal

from pydantic import BaseModel, Field

class Conversation(BaseModel):
    conversation_id: str
    created_at: str
    updated_at: str


class ConversationMessage(BaseModel):
    id: int
    conversation_id: str
    role: str
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    created_at: str