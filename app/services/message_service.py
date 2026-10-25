from __future__ import annotations

import logging
from typing import Any

from app.database.repositories.conversation_repository import (
    ConversationRepository,
)

logger = logging.getLogger(__name__)


class MessageService:
    def __init__(
        self,
        repository: ConversationRepository | None = None,
        history_limit: int = 12,
    ) -> None:
        if history_limit < 1:
            raise ValueError("history_limit must be at least 1")

        self.repository = repository or ConversationRepository()
        self.history_limit = history_limit

    def get_history(
        self,
        *,
        conversation_id: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        effective_limit = (
            self.history_limit if limit is None else limit
        )

        if effective_limit < 1:
            raise ValueError("limit must be at least 1")

        return self.repository.get_history(
            conversation_id=conversation_id,
            limit=effective_limit,
        )

    def save_user_message(
        self,
        *,
        conversation_id: str,
        content: str,
    ) -> dict[str, Any]:
        return self.repository.create_message(
            conversation_id=conversation_id,
            role="user",
            content=content,
        )

    def save_assistant_message(
        self,
        *,
        conversation_id: str,
        content: str,
        tool_calls_json: str | None = None,
    ) -> dict[str, Any]:
        return self.repository.create_message(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            tool_calls_json=tool_calls_json,
        )

    def save_tool_call_message(
        self,
        *,
        conversation_id: str,
        tool_calls_json: str,
    ) -> dict[str, Any]:
        return self.repository.create_message(
            conversation_id=conversation_id,
            role="assistant",
            content="",
            tool_calls_json=tool_calls_json,
        )

    def save_tool_result(
        self,
        *,
        conversation_id: str,
        content: str,
        tool_call_id: str,
        tool_name: str,
    ) -> dict[str, Any]:
        return self.repository.create_message(
            conversation_id=conversation_id,
            role="tool",
            content=content,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
        )