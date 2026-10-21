
from __future__ import annotations

import json
import uuid
from typing import Any

from app.database.connection import DatabaseConnection
from app.models.conversation import Conversation


class ConversationRepository:
    def __init__(
        self,
        database: DatabaseConnection | None = None,
    ) -> None:
        self.database = database or DatabaseConnection()

    def create(self, title: str | None = None) -> Conversation:
        conversation_id = str(uuid.uuid4())

        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO conversations (id, title)
                VALUES (?, ?)
                """,
                (conversation_id, title),
            )

            cursor = connection.execute(
                """
                SELECT
                    id AS conversation_id,
                    title,
                    created_at,
                    updated_at
                FROM conversations
                WHERE id = ?
                """,
                (conversation_id,),
            )
            row = cursor.fetchone()

        if row is None:
            raise RuntimeError("Failed to create conversation")

        return Conversation(**dict(row))

    def get_by_id(
        self,
        conversation_id: str,
    ) -> Conversation | None:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                SELECT
                    id AS conversation_id,
                    title,
                    created_at,
                    updated_at
                FROM conversations
                WHERE id = ?
                """,
                (conversation_id,),
            )
            row = cursor.fetchone()

        return Conversation(**dict(row)) if row is not None else None

    def exists(self, conversation_id: str) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                SELECT 1
                FROM conversations
                WHERE id = ?
                """,
                (conversation_id,),
            )
            return cursor.fetchone() is not None

    def create_message(
        self,
        conversation_id: str,
        role: str,
        content: str | None,
        tool_calls_json: str | None = None,
        tool_call_id: str | None = None,
        tool_name: str | None = None,
    ) -> str:
        message_id = str(uuid.uuid4())

        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO conversation_messages (
                    id,
                    conversation_id,
                    role,
                    content,
                    tool_calls_json,
                    tool_call_id,
                    tool_name
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    conversation_id,
                    role,
                    content,
                    tool_calls_json,
                    tool_call_id,
                    tool_name,
                ),
            )

            connection.execute(
                """
                UPDATE conversations
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (conversation_id,),
            )

        return message_id

    def get_message_by_id(
        self,
        conversation_id: str,
        message_id: str,
    ) -> dict[str, Any] | None:
        with self.database.connect() as connection:
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

        return dict(row) if row is not None else None

    def get_messages(
        self,
        conversation_id: str,
    ) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
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
                ORDER BY rowid ASC
                """,
                (conversation_id,),
            )

            return [dict(row) for row in cursor.fetchall()]
