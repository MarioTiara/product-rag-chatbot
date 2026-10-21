
from __future__ import annotations

import json
from typing import Any

from app.database.repositories.conversation_repository import ConversationRepository
from app.models.conversation import Conversation, ConversationMessage


class ConversationNotFoundError(LookupError):
    pass


class ConversationStore:
    def __init__(
        self,
        repository: ConversationRepository | None = None,
    ) -> None:
        self.repository = repository or ConversationRepository()

    def create_conversation(
        self,
        title: str | None = None,
    ) -> Conversation:
        return self.repository.create(title=title)

    def get_conversation(self, conversation_id: str) -> Conversation:
        conversation = self.repository.get_by_id(conversation_id)

        if conversation is None:
            raise ConversationNotFoundError(conversation_id)

        return conversation

    def conversation_exists(self, conversation_id: str) -> bool:
        return self.repository.exists(conversation_id)

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str | None = None,
        *,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_call_id: str | None = None,
        tool_name: str | None = None,
    ) -> ConversationMessage:
        self._ensure_conversation_exists(conversation_id)

        tool_calls_json = (
            json.dumps(tool_calls, ensure_ascii=False)
            if tool_calls
            else None
        )

        message_id = self.repository.create_message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tool_calls_json=tool_calls_json,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
        )

        return self.get_message_by_id(
            conversation_id=conversation_id,
            message_id=message_id,
        )

    def add_messages(
        self,
        conversation_id: str,
        messages: list[dict[str, Any]],
    ) -> None:
        for message in messages:
            self.add_message(
                conversation_id=conversation_id,
                role=message["role"],
                content=message.get("content"),
                tool_calls=message.get("tool_calls"),
                tool_call_id=message.get("tool_call_id"),
                tool_name=message.get("tool_name"),
            )

    def get_message_by_id(
        self,
        conversation_id: str,
        message_id: str,
    ) -> ConversationMessage:
        row = self.repository.get_message_by_id(
            conversation_id=conversation_id,
            message_id=message_id,
        )

        if row is None:
            raise ConversationNotFoundError(
                f"Message '{message_id}' not found in conversation '{conversation_id}'."
            )

        return self._row_to_message(row)

    def get_messages(
        self,
        conversation_id: str,
        limit: int | None = None,
    ) -> list[ConversationMessage]:
        self._ensure_conversation_exists(conversation_id)

        rows = self.repository.get_messages(conversation_id)

        return self._normalize_message_window(rows, limit)

    def _ensure_conversation_exists(self, conversation_id: str) -> None:
        if not self.repository.exists(conversation_id):
            raise ConversationNotFoundError(conversation_id)

    @staticmethod
    def _normalize_message_window(
        rows: list[dict[str, Any]],
        limit: int | None = None,
    ) -> list[ConversationMessage]:
        if not rows:
            return []

        if limit is not None:
            if limit <= 0:
                return []

            if len(rows) > limit:
                start_index = len(rows) - limit

                # Preserve preceding tool messages when the window
                # would otherwise start in the middle of tool results.
                while (
                    start_index > 0
                    and rows[start_index]["role"] == "tool"
                ):
                    start_index -= 1

                rows = rows[start_index:]

        return [
            ConversationStore._row_to_message(row)
            for row in rows
        ]

    @staticmethod
    def _row_to_message(
        row: dict[str, Any],
    ) -> ConversationMessage:
        tool_calls_json = row.get("tool_calls_json")
        tool_calls = (
            json.loads(tool_calls_json)
            if tool_calls_json
            else None
        )

        return ConversationMessage(
            id=str(row["id"]),
            conversation_id=row["conversation_id"],
            role=row["role"],
            content=row.get("content"),
            tool_calls=tool_calls,
            tool_call_id=row.get("tool_call_id"),
            tool_name=row.get("tool_name"),
            created_at=row["created_at"],
        )
