
from __future__ import annotations

from typing import Any

from app.database.connection import DatabaseConnection
from app.core.constants.constant import VALID_CHANNELS


class ChannelIdentityRepository:
    def __init__(
        self,
        database: DatabaseConnection | None = None,
    ) -> None:
        self.database = database or DatabaseConnection()

    def create(
        self,
        *,
        user_id: str,
        channel: str,
        channel_user_id: str,
    ) -> dict[str, Any]:
        if channel not in VALID_CHANNELS:
            raise ValueError("Unsupported channel")

        with self.database.connect() as connection:
            row = connection.execute(
                """
                INSERT INTO channel_identities (
                    user_id,
                    channel,
                    channel_user_id
                )
                VALUES (%s, %s, %s)
                RETURNING *
                """,
                (user_id, channel, channel_user_id),
            ).fetchone()

        return row

    def get_by_id(
        self,
        identity_id: int,
    ) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM channel_identities
                WHERE id = %s
                """,
                (identity_id,),
            ).fetchone()

        return row

    def get_by_channel_user(
        self,
        *,
        channel: str,
        channel_user_id: str,
    ) -> dict[str, Any] | None:
        if channel not in VALID_CHANNELS:
            raise ValueError("Unsupported channel")

        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM channel_identities
                WHERE channel = %s
                  AND channel_user_id = %s
                """,
                (channel, channel_user_id),
            ).fetchone()

        return row

    def list_by_user(
        self,
        user_id: str,
    ) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM channel_identities
                WHERE user_id = %s
                ORDER BY id ASC
                """,
                (user_id,),
            ).fetchall()

        return rows

    def update_user(
        self,
        *,
        identity_id: int,
        user_id: str,
    ) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE channel_identities
                SET user_id = %s
                WHERE id = %s
                """,
                (user_id, identity_id),
            )

        return cursor.rowcount > 0

    def delete(
        self,
        identity_id: int,
    ) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM channel_identities
                WHERE id = %s
                """,
                (identity_id,),
            )

        return cursor.rowcount > 0
