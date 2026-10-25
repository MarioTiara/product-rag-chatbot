
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

    @property
    def conversations(self) -> ConversationStore:
        """Backward-compatible self-reference used by older code paths."""
        return self

    def create_conversation(
        self,
        title: str | None = None,
        user_id: str | None = None,
    ) -> Conversation:
        return self.repository.create_conversation(
            user_id=user_id,
            title=title,
        )

    def get_conversation(self, conversation_id: str) -> Conversation:
        return self.repository.get_conversation(conversation_id)

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

    def create_message(
        self,
        conversation_id: str,
        role: str,
        content: str | None = None,
        *,
        tool_calls_json: str | None = None,
        tool_call_id: str | None = None,
        tool_name: str | None = None,
    ) -> ConversationMessage:
        tool_calls = (
            json.loads(tool_calls_json)
            if tool_calls_json
            else None
        )

        return self.add_message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
        )

    def get_history(
        self,
        conversation_id: str,
        limit: int | None = None,
    ) -> list[ConversationMessage]:
        return self.get_messages(conversation_id=conversation_id, limit=limit)

    def prepare_message(
        self,
        *,
        message: str,
        channel: str | None = None,
        channel_chat_id: str | None = None,
        channel_thread_id: str = "",
        channel_user_id: str | None = None,
        conversation_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        if channel is not None:
            raise ValueError("Channel conversations are not supported here")

        if conversation_id is None:
            conversation = self.create_conversation(
                title=message[:80],
                user_id=user_id,
            )
            conversation_id = conversation["id"]
        else:
            conversation = self.get_conversation(conversation_id)

            if conversation is None:
                raise ConversationNotFoundError(conversation_id)

        history = self.get_history(conversation_id=conversation_id, limit=12)
        user_message = self.create_message(
            conversation_id=conversation_id,
            role="user",
            content=message,
        )

        return {
            "conversation_id": conversation_id,
            "channel_conversation_id": None,
            "user_message_id": user_message.id,
            "history": history,
            "conversation": conversation,
        }

    def save_assistant_message(
        self,
        *,
        conversation_id: str,
        content: str,
        tool_calls_json: str | None = None,
    ) -> ConversationMessage:
        return self.create_message(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            tool_calls_json=tool_calls_json,
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
        row = self.repository.get_message(message_id)

        if row is None or row.get("conversation_id") != conversation_id:
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

        rows = self.repository.get_history(
            conversation_id=conversation_id,
            limit=limit or 12,
        )

        return self._normalize_message_window(rows, limit)

    def _ensure_conversation_exists(self, conversation_id: str) -> None:
        if self.repository.get_conversation(conversation_id) is None:
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
