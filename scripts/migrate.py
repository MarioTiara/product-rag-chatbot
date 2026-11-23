
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import psycopg

from app.core.configs.config import get_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = PROJECT_ROOT / "app" / "database" / "migrations" / "postgres"

logger = logging.getLogger(__name__)
settings = get_settings()


def run_migrations(
    database_url: str = settings.database_url,
) -> None:
    """Apply pending SQL migrations to PostgreSQL."""

    if not MIGRATIONS_DIR.is_dir():
        raise FileNotFoundError(
            f"Migrations directory not found: {MIGRATIONS_DIR}"
        )

    logger.info("Starting database migrations")
    logger.info("Database: PostgreSQL")
    logger.info("Migrations directory: %s", MIGRATIONS_DIR)

    with psycopg.connect(database_url) as connection:

        # Create migration tracking table.
        connection.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL
                    DEFAULT CURRENT_TIMESTAMP
            )
        """)

        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

        if not migration_files:
            logger.warning(
                "No SQL migration files found in %s",
                MIGRATIONS_DIR,
            )
            return

        for migration_file in migration_files:
            version = migration_file.name

            applied = connection.execute(
                """
                SELECT 1
                FROM schema_migrations
                WHERE version = %s
                """,
                (version,),
            ).fetchone()

            if applied:
                logger.info(
                    "Skipping migration %s: already applied",
                    version,
                )
                continue

            sql = migration_file.read_text(encoding="utf-8")

            logger.info("Applying migration: %s", version)

            try:
                # Migration SQL and tracking record share one transaction.
                with connection.transaction():
                    connection.execute(sql, prepare=False)

                    connection.execute(
                        """
                        INSERT INTO schema_migrations (version)
                        VALUES (%s)
                        """,
                        (version,),
                    )

                logger.info("Applied migration: %s", version)

            except Exception:
                logger.exception(
                    "Migration failed: %s",
                    version,
                )
                raise

        logger.info("Database migrations completed successfully")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Apply pending PostgreSQL database migrations."
    )

    parser.add_argument(
        "--database-url",
        default=settings.database_url,
        help="PostgreSQL connection URL.",
    )

    args = parser.parse_args()
    run_migrations(database_url=args.database_url)


if __name__ == "__main__":
    main()
