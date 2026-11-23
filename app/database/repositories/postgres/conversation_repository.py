
from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.database.connection import DatabaseConnection


class ConversationRepository:
    VALID_CHANNELS = {"telegram", "whatsapp", "web"}
    VALID_ROLES = {"system", "user", "assistant", "tool"}
    VALID_MESSAGE_TYPES = {"user", "assistant"}
    VALID_DELIVERY_STATUSES = {
        "received", "pending", "sent", "failed"
    }

    def __init__(
        self,
        database: DatabaseConnection | None = None,
    ) -> None:
        self.database = database or DatabaseConnection()

    # --------------------------------------------------
    # CONVERSATIONS
    # --------------------------------------------------

    def create_conversation(
        self,
        *,
        user_id: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        conversation_id = str(uuid4())

        with self.database.connect() as connection:
            row = connection.execute(
                """
                INSERT INTO conversations (id, user_id, title)
                VALUES (%s, %s, %s)
                RETURNING *
                """,
                (conversation_id, user_id, title),
            ).fetchone()

        return row

    def get_conversation(
        self,
        conversation_id: str,
    ) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM conversations
                WHERE id = %s
                """,
                (conversation_id,),
            ).fetchone()

        return row

    def list_conversations(
        self,
        *,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        if offset < 0:
            raise ValueError("offset cannot be negative")

        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM conversations
                WHERE user_id = %s
                ORDER BY updated_at DESC, id DESC
                LIMIT %s OFFSET %s
                """,
                (user_id, limit, offset),
            ).fetchall()

        return rows

    def update_conversation_title(
        self,
        *,
        conversation_id: str,
        title: str,
    ) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE conversations
                SET title = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (title, conversation_id),
            )

        return cursor.rowcount > 0

    def delete_conversation(
        self,
        conversation_id: str,
    ) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM conversations
                WHERE id = %s
                """,
                (conversation_id,),
            )

        return cursor.rowcount > 0

    # --------------------------------------------------
    # CHANNEL CONVERSATIONS
    # --------------------------------------------------

    def get_or_create_channel_conversation(
        self,
        *,
        conversation_id: str,
        channel: str,
        channel_chat_id: str,
        channel_thread_id: str = "",
    ) -> dict[str, Any]:
        if channel not in self.VALID_CHANNELS:
            raise ValueError("Unsupported channel")

        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO channel_conversations (
                    conversation_id,
                    channel,
                    channel_chat_id,
                    channel_thread_id
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (
                    channel,
                    channel_chat_id,
                    channel_thread_id
                ) DO NOTHING
                """,
                (
                    conversation_id,
                    channel,
                    channel_chat_id,
                    channel_thread_id,
                ),
            )

            row = connection.execute(
                """
                SELECT *
                FROM channel_conversations
                WHERE channel = %s
                  AND channel_chat_id = %s
                  AND channel_thread_id = %s
                """,
                (
                    channel,
                    channel_chat_id,
                    channel_thread_id,
                ),
            ).fetchone()

        return row

    def get_channel_conversation(
        self,
        *,
        channel: str,
        channel_chat_id: str,
        channel_thread_id: str = "",
    ) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM channel_conversations
                WHERE channel = %s
                  AND channel_chat_id = %s
                  AND channel_thread_id = %s
                """,
                (channel, channel_chat_id, channel_thread_id),
            ).fetchone()

        return row

    def list_channel_conversations(
        self,
        conversation_id: str,
    ) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM channel_conversations
                WHERE conversation_id = %s
                ORDER BY id ASC
                """,
                (conversation_id,),
            ).fetchall()

        return rows

    # --------------------------------------------------
    # CONVERSATION MESSAGES
    # --------------------------------------------------

    def create_message(
        self,
        *,
        conversation_id: str,
        role: str,
        content: str | None,
        tool_calls_json: str | None = None,
        tool_call_id: str | None = None,
        tool_name: str | None = None,
    ) -> dict[str, Any]:
        if role not in self.VALID_ROLES:
            raise ValueError("Unsupported message role")

        message_id = str(uuid4())

        with self.database.connect() as connection:
            # Lock the conversation row to serialize sequence allocation.
            connection.execute(
                """
                SELECT id
                FROM conversations
                WHERE id = %s
                FOR UPDATE
                """,
                (conversation_id,),
            )

            sequence_row = connection.execute(
                """
                SELECT COALESCE(MAX(sequence_number), 0) + 1
                    AS next_sequence
                FROM conversation_messages
                WHERE conversation_id = %s
                """,
                (conversation_id,),
            ).fetchone()

            sequence_number = sequence_row["next_sequence"]

            row = connection.execute(
                """
                INSERT INTO conversation_messages (
                    id,
                    conversation_id,
                    sequence_number,
                    role,
                    content,
                    tool_calls_json,
                    tool_call_id,
                    tool_name
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    message_id,
                    conversation_id,
                    sequence_number,
                    role,
                    content,
                    tool_calls_json,
                    tool_call_id,
                    tool_name,
                ),
            ).fetchone()

            connection.execute(
                """
                UPDATE conversations
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (conversation_id,),
            )

        return row

    def get_message(
        self,
        message_id: str,
    ) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM conversation_messages
                WHERE id = %s
                """,
                (message_id,),
            ).fetchone()

        return row

    def get_history(
        self,
        *,
        conversation_id: str,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")

        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM (
                    SELECT *
                    FROM conversation_messages
                    WHERE conversation_id = %s
                    ORDER BY sequence_number DESC
                    LIMIT %s
                ) AS recent_messages
                ORDER BY sequence_number ASC
                """,
                (conversation_id, limit),
            ).fetchall()

        return rows

    # --------------------------------------------------
    # CHANNEL MESSAGES
    # --------------------------------------------------

    def create_channel_message(
        self,
        *,
        internal_message_id: str,
        channel_conversation_id: int,
        channel_message_id: str,
        message_type: str,
        delivery_status: str = "received",
    ) -> dict[str, Any]:
        if message_type not in self.VALID_MESSAGE_TYPES:
            raise ValueError("Unsupported message type")

        if delivery_status not in self.VALID_DELIVERY_STATUSES:
            raise ValueError("Unsupported delivery status")

        with self.database.connect() as connection:
            row = connection.execute(
                """
                INSERT INTO channel_messages (
                    internal_message_id,
                    channel_conversation_id,
                    channel_message_id,
                    message_type,
                    delivery_status
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    internal_message_id,
                    channel_conversation_id,
                    channel_message_id,
                    message_type,
                    delivery_status,
                ),
            ).fetchone()

        return row

    def get_channel_message(
        self,
        *,
        channel_conversation_id: int,
        channel_message_id: str,
    ) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM channel_messages
                WHERE channel_conversation_id = %s
                  AND channel_message_id = %s
                """,
                (channel_conversation_id, channel_message_id),
            ).fetchone()

        return row

    def update_delivery_status(
        self,
        *,
        channel_message_id: int,
        delivery_status: str,
    ) -> bool:
        if delivery_status not in self.VALID_DELIVERY_STATUSES:
            raise ValueError("Unsupported delivery status")

        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE channel_messages
                SET delivery_status = %s
                WHERE id = %s
                """,
                (delivery_status, channel_message_id),
            )

        return cursor.rowcount > 0
