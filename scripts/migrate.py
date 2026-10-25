
from __future__ import annotations

import argparse
import logging
import sqlite3
from pathlib import Path



from app.configs.config import get_settings
PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = PROJECT_ROOT / "app" / "database" / "migrations"

logger = logging.getLogger(__name__)

settings= get_settings()

def run_migrations(
    db_path: str | Path = settings.database_path,
) -> None:
    """Apply pending SQL migrations to the SQLite database."""
    db_path = Path(db_path)

    if not db_path.is_absolute():
        db_path = PROJECT_ROOT / db_path

    if not MIGRATIONS_DIR.is_dir():
        raise FileNotFoundError(
            f"Migrations directory not found: {MIGRATIONS_DIR}"
        )

    # Ensure the database directory exists.
    db_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Starting database migrations")
    logger.info("Database: %s", db_path)
    logger.info("Migrations directory: %s", MIGRATIONS_DIR)

    connection = sqlite3.connect(db_path)

    try:
        connection.execute("PRAGMA foreign_keys = ON")

        connection.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(255) PRIMARY KEY,
                applied_at VARCHAR(30) NOT NULL
                    DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.commit()

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
                WHERE version = ?
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
                # executescript manages its own transaction here.
                # The migration and version record are committed together.
                escaped_version = version.replace("'", "''")

                connection.executescript(
                    f"""
                    BEGIN IMMEDIATE;

                    {sql}

                    INSERT INTO schema_migrations (version)
                    VALUES ('{escaped_version}');

                    COMMIT;
                    """
                )

                logger.info("Applied migration: %s", version)

            except Exception:
                if connection.in_transaction:
                    connection.rollback()

                logger.exception(
                    "Migration failed: %s",
                    version,
                )
                raise

        logger.info("Database migrations completed successfully")

    finally:
        connection.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Apply pending SQLite database migrations."
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=settings.database_path,
        help="Path to the SQLite database file.",
    )

    args = parser.parse_args()
    run_migrations(db_path=args.db_path)


if __name__ == "__main__":
    main()
