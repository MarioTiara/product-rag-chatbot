from __future__ import annotations

import csv
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "products.sqlite3"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS products (
    sku TEXT PRIMARY KEY,
    brand TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT,
    price REAL,
    processor_name TEXT,
    processor_brand TEXT,
    ram_expandable TEXT,
    ram TEXT,
    ram_type TEXT,
    ghz TEXT,
    display_type TEXT,
    display TEXT,
    gpu TEXT,
    gpu_brand TEXT,
    ssd TEXT,
    hdd TEXT,
    stock INTEGER DEFAULT 0,
    battery_life TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

UPSERT_SQL = """
INSERT INTO products (
    sku, brand, name, category, price, processor_name, processor_brand,
    ram_expandable, ram, ram_type, ghz, display_type, display,
    gpu, gpu_brand, ssd, hdd, stock, battery_life, updated_at
)
VALUES (
    :sku, :brand, :name, :category, :price, :processor_name, :processor_brand,
    :ram_expandable, :ram, :ram_type, :ghz, :display_type, :display,
    :gpu, :gpu_brand, :ssd, :hdd, :stock, :battery_life, CURRENT_TIMESTAMP
)
ON CONFLICT(sku) DO UPDATE SET
    brand = excluded.brand,
    name = excluded.name,
    category = excluded.category,
    price = excluded.price,
    processor_name = excluded.processor_name,
    processor_brand = excluded.processor_brand,
    ram_expandable = excluded.ram_expandable,
    ram = excluded.ram,
    ram_type = excluded.ram_type,
    ghz = excluded.ghz,
    display_type = excluded.display_type,
    display = excluded.display,
    gpu = excluded.gpu,
    gpu_brand = excluded.gpu_brand,
    ssd = excluded.ssd,
    hdd = excluded.hdd,
    stock = excluded.stock,
    battery_life = excluded.battery_life,
    updated_at = CURRENT_TIMESTAMP
"""


class DatabaseService:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connection() as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(CREATE_TABLE_SQL)
            self._ensure_column(connection, "products", "category", "TEXT")
            connection.commit()

    def seed_from_csv(self, csv_path: str | Path) -> int:
        self.initialize()
        rows = self._load_csv_rows(csv_path)

        if not rows:
            return 0

        with self.connection() as connection:
            connection.executemany(UPSERT_SQL, rows)
            connection.commit()

        return len(rows)

    def list_products(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        with self.connection() as connection:
            cursor = connection.execute(
                """
                SELECT *
                FROM products
                ORDER BY brand, name
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_product_by_sku(self, sku: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            cursor = connection.execute(
                "SELECT * FROM products WHERE sku = ?",
                (sku.strip(),),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def search_products(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        term = f"%{query.strip()}%"
        with self.connection() as connection:
            cursor = connection.execute(
                """
                SELECT *
                FROM products
                WHERE sku LIKE ? OR brand LIKE ? OR name LIKE ?
                ORDER BY brand, name
                LIMIT ?
                """,
                (term, term, term, limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    def _load_csv_rows(self, csv_path: str | Path) -> list[dict[str, Any]]:
        path = Path(csv_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path

        with path.open(newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            rows: list[dict[str, Any]] = []
            for row in reader:
                normalized = self._normalize_row(row)
                if normalized:
                    rows.append(normalized)
            return rows

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any] | None:
        sku = self._clean_text(row.get("SKU"))
        brand = self._clean_text(row.get("Brand"))
        raw_name = self._clean_text(row.get("Name"))
        name, category = self._split_name_and_category(raw_name)

        if not sku or not brand or not name:
            return None

        return {
            "sku": sku,
            "brand": brand,
            "name": name,
            "category": category,
            "price": self._clean_float(row.get("Price")),
            "processor_name": self._clean_text(row.get("Processor_Name")),
            "processor_brand": self._clean_text(row.get("Processor_Brand")),
            "ram_expandable": self._clean_text(row.get("RAM_Expandable")),
            "ram": self._clean_text(row.get("RAM")),
            "ram_type": self._clean_text(row.get("RAM_TYPE")),
            "ghz": self._clean_text(row.get("Ghz")),
            "display_type": self._clean_text(row.get("Display_type")),
            "display": self._clean_text(row.get("Display")),
            "gpu": self._clean_text(row.get("GPU")),
            "gpu_brand": self._clean_text(row.get("GPU_Brand")),
            "ssd": self._clean_text(row.get("SSD")),
            "hdd": self._clean_text(row.get("HDD")),
            "stock": self._clean_int(row.get("Stock")) or 0,
            "battery_life": self._clean_text(row.get("Battery_Life")),
        }

    @staticmethod
    def _split_name_and_category(value: str | None) -> tuple[str | None, str | None]:
        if not value:
            return None, None

        parts = [part.strip() for part in value.split("::") if part.strip()]
        if not parts:
            return None, None

        name = parts[0]
        category = parts[-1].lower() if len(parts) > 1 else None
        return name, category

    @staticmethod
    def _ensure_column(
        connection: sqlite3.Connection,
        table_name: str,
        column_name: str,
        column_type: str,
    ) -> None:
        cursor = connection.execute(f"PRAGMA table_info({table_name})")
        columns = {row[1] for row in cursor.fetchall()}
        if column_name not in columns:
            connection.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
            )

    @staticmethod
    def _clean_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower() in {"nan", "none", "null"}:
            return None
        return text

    @staticmethod
    def _clean_float(value: Any) -> float | None:
        text = DatabaseService._clean_text(value)
        if text is None:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    @staticmethod
    def _clean_int(value: Any) -> int | None:
        text = DatabaseService._clean_text(value)
        if text is None:
            return None
        try:
            return int(float(text))
        except ValueError:
            return None
