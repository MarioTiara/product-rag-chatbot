from __future__ import annotations

import argparse
import logging
from pathlib import Path

from app.configs import config
from scripts.migrate import run_migrations
from scripts.data_seed import seed_products

logger = logging.getLogger(__name__)
settings= config.get_settings()

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Initialize database schema and seed product data."
    )
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=Path("data/product.csv"),
        help="Path to the product CSV file.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=settings.database_path,
        help="Path to the SQLite database file.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Number of products processed per batch.",
    )
    return parser


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    args = build_parser().parse_args()

    if args.batch_size < 1:
        raise ValueError("--batch-size must be greater than 0.")

    logger.info("Starting database initialization.")

    # Step 1: Create/update database schema.
    run_migrations(db_path=args.db_path)

    logger.info("Database migrations completed.")

    # Step 2: Seed data only after migrations succeed.
    seed_products(
        csv_path=args.csv_path,
        db_path=args.db_path,
        batch_size=args.batch_size,
    )

    logger.info("Database initialization completed successfully.")


if __name__ == "__main__":
    main()