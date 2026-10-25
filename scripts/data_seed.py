
from __future__ import annotations

import argparse
import csv
import logging
import uuid
from pathlib import Path
from typing import Any, Iterator

from app.database.connection import DatabaseConnection
from app.configs import config
from app.database.repositories.product_repository import ProductRepository


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV_PATH = PROJECT_ROOT / "data" / "product.csv"

logger = logging.getLogger(__name__)
settings= config.get_settings()

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seed SQLite with product CSV data."
    )
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help="Path to the product CSV file.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=s,
        help="Path to the SQLite database file.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Number of products processed per batch.",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop processing when a batch or row fails.",
    )
    return parser


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def iter_batches(
    reader: csv.DictReader,
    batch_size: int,
) -> Iterator[list[tuple[int, dict[str, Any]]]]:
    batch: list[tuple[int, dict[str, Any]]] = []

    for line_number, row in enumerate(reader, start=2):
        batch.append((line_number, row))

        if len(batch) >= batch_size:
            yield batch
            batch = []

    if batch:
        yield batch


def seed_products(
    csv_path: str | Path = DEFAULT_CSV_PATH,
    db_path: str | Path = settings.database_path,
    batch_size: int = 500,
    stop_on_error: bool = False,
) -> dict[str, Any]:
    """Import product CSV data in independently committed batches."""
    if batch_size < 1:
        raise ValueError("batch_size must be greater than 0.")

    csv_path = resolve_path(Path(csv_path))
    db_path = resolve_path(Path(db_path))

    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    repository = ProductRepository(DatabaseConnection(db_path))

    result: dict[str, Any] = {
        "total": 0,
        "succeeded": 0,
        "failed": 0,
        "failed_batches": 0,
        "failed_rows": [],
    }

    logger.info("Starting product seed")
    logger.info("CSV: %s", csv_path)
    logger.info("Database: %s", db_path)
    logger.info("Batch size: %s", batch_size)

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError("CSV file is empty or has no header.")

        for batch_number, raw_batch in enumerate(
            iter_batches(reader, batch_size),
            start=1,
        ):
            result["total"] += len(raw_batch)

            valid_products: list[dict[str, Any]] = []
            valid_line_numbers: list[int] = []
            batch_has_invalid_rows = False

            for line_number, row in raw_batch:
                try:
                    product = normalize_product(row)
                    valid_products.append(product)
                    valid_line_numbers.append(line_number)
                except (ValueError, TypeError) as exc:
                    batch_has_invalid_rows = True
                    result["failed"] += 1
                    result["failed_rows"].append({
                        "line": line_number,
                        "product_code": row.get("Product_Code"),
                        "error": str(exc),
                    })

                    logger.error(
                        "Invalid CSV row %s: %s",
                        line_number,
                        exc,
                    )

            if stop_on_error and batch_has_invalid_rows:
                logger.error(
                    "Stopping at batch %s due to invalid CSV rows.",
                    batch_number,
                )
                break

            if not valid_products:
                logger.warning(
                    "Batch %s skipped: no valid products.",
                    batch_number,
                )
                continue

            try:
                # Each call must be transactional in the repository.
                affected = repository.upsert_many(valid_products)

                result["succeeded"] += affected

                logger.info(
                    "Batch %s completed: %s rows affected.",
                    batch_number,
                    affected,
                )

            except Exception as exc:
                result["failed_batches"] += 1
                result["failed"] += len(valid_products)

                for line_number, product in zip(
                    valid_line_numbers,
                    valid_products,
                ):
                    result["failed_rows"].append({
                        "line": line_number,
                        "product_code": product["product_code"],
                        "error": f"Batch {batch_number} failed: {exc}",
                    })

                logger.exception(
                    "Batch %s failed. CSV lines %s-%s.",
                    batch_number,
                    raw_batch[0][0],
                    raw_batch[-1][0],
                )

                if stop_on_error:
                    break

    failed_rows = result["failed_rows"]

    if failed_rows:
        error_path = csv_path.with_name(
            f"{csv_path.stem}_errors.csv"
        )

        with error_path.open(
            "w",
            encoding="utf-8-sig",
            newline="",
        ) as error_file:
            writer = csv.DictWriter(
                error_file,
                fieldnames=["line", "product_code", "error"],
            )
            writer.writeheader()
            writer.writerows(failed_rows)

        logger.error("Error report saved to: %s", error_path)

    logger.info("=" * 60)
    logger.info("Product seed finished")
    logger.info("Total rows read: %s", result["total"])
    logger.info("Successfully affected: %s", result["succeeded"])
    logger.info("Failed rows: %s", result["failed"])
    logger.info("Failed batches: %s", result["failed_batches"])

    if result["failed"]:
        raise RuntimeError(
            f"Product seeding failed: {result['failed']} rows failed. "
            f"See the error report beside {csv_path}."
        )

    return result


def normalize_product(row: dict[str, str | None]) -> dict[str, Any]:
    """Normalize a CSV row to match the products table schema."""
    product_code = (row.get("Product_Code") or "").strip()
    brand = (row.get("Brand") or "").strip()
    name = (row.get("Name") or "").strip()

    if not product_code or not brand or not name:
        raise ValueError(
            "Missing required product fields: "
            f"product_code={product_code!r}, "
            f"brand={brand!r}, name={name!r}"
        )

    return {
        "id": str(uuid.uuid4()),
        "product_id": (row.get("Product ID") or "").strip() or None,
        "brand": brand,
        "model": (row.get("Model") or "").strip() or None,
        "product_code": product_code,
        "name": name,
        "os": (row.get("OS") or "").strip() or None,
        "price": parse_float(row.get("USD_Price")),
        "processor_name": (row.get("Processor_Name") or "").strip() or None,
        "processor_brand": (row.get("Processor_Brand") or "").strip() or None,
        "ram_expandable": parse_int(row.get("RAM_Expandable")) or 0,
        "ram_gb": parse_int(row.get("RAM_GB")),
        "ram_type": (row.get("RAM_TYPE") or "").strip() or None,
        "processor_ghz": parse_float(row.get("Processor_Ghz")),
        "display_type": (row.get("Display_type") or "").strip() or None,
        "display_inch": parse_float(row.get("Display_Inch")),
        "gpu": (row.get("GPU") or "").strip() or None,
        "gpu_brand": (row.get("GPU_Brand") or "").strip() or None,
        "ssd_gb": parse_int(row.get("SSD_GB")),
        "hdd_gb": parse_int(row.get("HDD_GB")),
        "stock": parse_int(row.get("Stock")) or 0,
        "battery_life": (row.get("Battery_Life") or "").strip() or None,
        "tags": (row.get("Tags") or "").strip() or None,
    }


def parse_int(value: str | None) -> int | None:
    if not value or not value.strip():
        return None

    try:
        return int(float(value.strip()))
    except ValueError:
        return None


def parse_float(value: str | None) -> float | None:
    if not value or not value.strip():
        return None

    try:
        return float(value.strip())
    except ValueError:
        return None


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    args = build_parser().parse_args()

    seed_products(
        csv_path=args.csv_path,
        db_path=args.db_path,
        batch_size=args.batch_size,
        stop_on_error=args.stop_on_error,
    )


if __name__ == "__main__":
    main()
