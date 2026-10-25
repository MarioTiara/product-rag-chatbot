
from __future__ import annotations

from typing import Any
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

class Conversation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    conversation_id: str = Field(alias="id")
    title:str | None= None 
    created_at: str
    updated_at: str


class ConversationMessage(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    created_at: str
