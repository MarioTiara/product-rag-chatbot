from __future__ import annotations

import argparse
from pathlib import Path

from app.database import DEFAULT_DB_PATH, DatabaseService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed SQLite with product CSV data.")
    parser.add_argument(
        "--csv-path",
        default=Path("data/prodct.csv"),
        help="Path to the product CSV file (default: data/prodct.csv).",
    )
    parser.add_argument(
        "--db-path",
        default=DEFAULT_DB_PATH,
        help="Path to the SQLite database file.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    service = DatabaseService(args.db_path)
    inserted = service.seed_from_csv(args.csv_path)
    print(f"Seeded {inserted} products into {service.db_path}")


if __name__ == "__main__":
    main()
