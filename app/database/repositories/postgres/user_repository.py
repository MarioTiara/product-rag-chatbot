
from __future__ import annotations

from uuid import uuid4

from app.database.connection import DatabaseConnection
from app.models.user import User


class UserRepository:
    def __init__(
        self,
        database: DatabaseConnection | None = None,
    ) -> None:
        self.database = database or DatabaseConnection()

    def create(
        self,
        *,
        display_name: str | None = None,
        email: str | None = None,
        password_hash: str | None = None,
    ) -> User:
        user_id = str(uuid4())

        with self.database.connect() as connection:
            row = connection.execute(
                """
                INSERT INTO users (
                    id,
                    display_name,
                    email,
                    password_hash
                )
                VALUES (%s, %s, %s, %s)
                RETURNING
                    id,
                    display_name,
                    email,
                    created_at,
                    updated_at
                """,
                (
                    user_id,
                    display_name,
                    email,
                    password_hash,
                ),
            ).fetchone()

        if row is None:
            raise RuntimeError("Failed to create user.")

        return User(**row)

    def get_by_id(
        self,
        user_id: str,
    ) -> User | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    display_name,
                    email,
                    created_at,
                    updated_at
                FROM users
                WHERE id = %s
                """,
                (user_id,),
            ).fetchone()

        return User(**row) if row is not None else None

    def get_by_email(
        self,
        email: str,
    ) -> User | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    display_name,
                    email,
                    created_at,
                    updated_at
                FROM users
                WHERE email = %s
                """,
                (email,),
            ).fetchone()

        return User(**row) if row is not None else None

    def get_password_hash_by_email(
        self,
        email: str,
    ) -> str | None:
        """Retrieve the password hash for authentication."""
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT password_hash
                FROM users
                WHERE email = %s
                """,
                (email,),
            ).fetchone()

        return row["password_hash"] if row is not None else None

    def update(
        self,
        *,
        user_id: str,
        display_name: str | None = None,
        email: str | None = None,
    ) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE users
                SET display_name = %s,
                    email = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (display_name, email, user_id),
            )

        return cursor.rowcount > 0

    def update_password_hash(
        self,
        *,
        user_id: str,
        password_hash: str,
    ) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE users
                SET password_hash = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (password_hash, user_id),
            )

        return cursor.rowcount > 0

    def delete(
        self,
        user_id: str,
    ) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM users
                WHERE id = %s
                """,
                (user_id,),
            )

        return cursor.rowcount > 0
