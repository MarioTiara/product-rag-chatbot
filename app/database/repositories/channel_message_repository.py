from __future__ import annotations

from typing import Any

from app.database.connection import DatabaseConnection


class ChannelMessageRepository:
    def __init__(
        self,
        database: DatabaseConnection | None = None,
    ) -> None:
        self.database = database or DatabaseConnection()

    def create(
        self,
        *,
        internal_message_id: str,
        channel_conversation_id: int,
        channel_message_id: str,
        message_type: str,
        delivery_status: str | None = None,
    ) -> int:
        if message_type not in {"user", "assistant"}:
            raise ValueError(
                "message_type must be 'user' or 'assistant'"
            )

        if delivery_status is None:
            delivery_status = (
                "received" if message_type == "user" else "sent"
            )

        if delivery_status not in {
            "received",
            "pending",
            "sent",
            "failed",
        }:
            raise ValueError("Invalid delivery_status")

        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO channel_messages (
                    internal_message_id,
                    channel_conversation_id,
                    channel_message_id,
                    message_type,
                    delivery_status
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    internal_message_id,
                    channel_conversation_id,
                    channel_message_id,
                    message_type,
                    delivery_status,
                ),
            )

            return cursor.lastrowid

    def get_by_id(
        self,
        message_id: int,
    ) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM channel_messages
                WHERE id = ?
                """,
                (message_id,),
            ).fetchone()

        return dict(row) if row is not None else None

    def get_by_channel_message(
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
                WHERE channel_conversation_id = ?
                  AND channel_message_id = ?
                """,
                (
                    channel_conversation_id,
                    channel_message_id,
                ),
            ).fetchone()

        return dict(row) if row is not None else None

    def get_by_internal_message_id(
        self,
        internal_message_id: str,
    ) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM channel_messages
                WHERE internal_message_id = ?
                ORDER BY id ASC
                """,
                (internal_message_id,),
            ).fetchall()

        return [dict(row) for row in rows]

    def list_by_chat(
        self,
        *,
        channel: str,
        channel_chat_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= 1000:
            raise ValueError(
                "limit must be between 1 and 1000"
            )

        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    cm.*,
                    cc.channel,
                    cc.channel_chat_id,
                    cc.channel_thread_id
                FROM channel_messages AS cm
                JOIN channel_conversations AS cc
                    ON cc.id = cm.channel_conversation_id
                WHERE cc.channel = ?
                  AND cc.channel_chat_id = ?
                ORDER BY cm.id DESC
                LIMIT ?
                """,
                (channel, channel_chat_id, limit),
            ).fetchall()

        return [dict(row) for row in rows]

    def update_delivery_status(
        self,
        *,
        message_id: int,
        delivery_status: str,
    ) -> bool:
        if delivery_status not in {
            "received",
            "pending",
            "sent",
            "failed",
        }:
            raise ValueError("Invalid delivery_status")

        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE channel_messages
                SET delivery_status = ?
                WHERE id = ?
                """,
                (delivery_status, message_id),
            )

        return cursor.rowcount > 0
