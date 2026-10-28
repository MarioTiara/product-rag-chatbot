from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ChatContext:
    conversation_id: str
    user_message_id: str
    channel_conversation_id: int | None
    messages: list[dict[str, Any]]
    history_count: int