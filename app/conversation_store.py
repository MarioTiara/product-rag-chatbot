from __future__ import annotations

import json
import uuid
from typing import Any

from app.database import DatabaseService
from app.models import Conversation, ConversationMessage


class ConversationNotFoundError(LookupError):
    pass


class ConversationStore:
    def __init__(self, database: DatabaseService | None = None) -> None:
        self.database = database or DatabaseService()
        self.database.initialize()

    def create_conversation(self, conversation_id: str | None = None) -> Conversation:
        conversation_id = conversation_id or str(uuid.uuid4())

        with self.database.connection() as connection:
            connection.execute(
                """
                INSERT INTO conversations (id)
                VALUES (?)
                """,
                (conversation_id,),
            )
            connection.commit()

        return self.get_conversation(conversation_id)

    def get_conversation(self, conversation_id: str) -> Conversation:
        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                SELECT id AS conversation_id, created_at, updated_at
                FROM conversations
                WHERE id = ?
                """,
                (conversation_id,),
            )
            row = cursor.fetchone()

        if row is None:
            raise ConversationNotFoundError(conversation_id)

        return Conversation.model_validate(dict(row))

    def conversation_exists(self, conversation_id: str) -> bool:
        with self.database.connection() as connection:
            cursor = connection.execute(
                "SELECT 1 FROM conversations WHERE id = ?",
                (conversation_id,),
            )
            return cursor.fetchone() is not None

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

        tool_calls_json = json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None

        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO conversation_messages (
                    conversation_id, role, content, tool_calls_json, tool_call_id, tool_name
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (conversation_id, role, content, tool_calls_json, tool_call_id, tool_name),
            )
            connection.execute(
                """
                UPDATE conversations
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (conversation_id,),
            )
            connection.commit()

            message_id = int(cursor.lastrowid)

        return self.get_message_by_id(conversation_id, message_id)

    def add_messages(self, conversation_id: str, messages: list[dict[str, Any]]) -> None:
        for message in messages:
            self.add_message(
                conversation_id=conversation_id,
                role=message["role"],
                content=message.get("content"),
                tool_calls=message.get("tool_calls"),
                tool_call_id=message.get("tool_call_id"),
                tool_name=message.get("tool_name"),
            )

    def get_message_by_id(self, conversation_id: str, message_id: int) -> ConversationMessage:
        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                SELECT
                    id,
                    conversation_id,
                    role,
                    content,
                    tool_calls_json,
                    tool_call_id,
                    tool_name,
                    created_at
                FROM conversation_messages
                WHERE conversation_id = ? AND id = ?
                """,
                (conversation_id, message_id),
            )
            row = cursor.fetchone()

        if row is None:
            raise ConversationNotFoundError(conversation_id)

        return self._row_to_message(dict(row))

    def get_messages(self, conversation_id: str, limit: int | None = None) -> list[ConversationMessage]:
        self._ensure_conversation_exists(conversation_id)

        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                SELECT
                    id,
                    conversation_id,
                    role,
                    content,
                    tool_calls_json,
                    tool_call_id,
                    tool_name,
                    created_at
                FROM conversation_messages
                WHERE conversation_id = ?
                ORDER BY id ASC
                """,
                (conversation_id,),
            )
            rows = [dict(row) for row in cursor.fetchall()]

        return self._normalize_message_window(rows, limit)

    def _normalize_message_window(
        self,
        rows: list[dict[str, Any]],
        limit: int | None = None,
    ) -> list[ConversationMessage]:
        if not rows:
            return []

        if limit is not None and len(rows) > limit:
            start_index = len(rows) - limit
            while start_index > 0 and rows[start_index]["role"] == "tool":
                start_index -= 1
            rows = rows[start_index:]

        return [self._row_to_message(row) for row in rows]

    def _ensure_conversation_exists(self, conversation_id: str) -> None:
        if not self.conversation_exists(conversation_id):
            raise ConversationNotFoundError(conversation_id)

    @staticmethod
    def _row_to_message(row: dict[str, Any]) -> ConversationMessage:
        tool_calls_json = row.get("tool_calls_json")
        tool_calls = json.loads(tool_calls_json) if tool_calls_json else None
        return ConversationMessage(
            id=row["id"],
            conversation_id=row["conversation_id"],
            role=row["role"],
            content=row.get("content"),
            tool_calls=tool_calls,
            tool_call_id=row.get("tool_call_id"),
            tool_name=row.get("tool_name"),
            created_at=row["created_at"],
        )
