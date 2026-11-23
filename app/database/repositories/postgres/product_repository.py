
from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from app.database.connection import DatabaseConnection
from app.models.product import Product
from app.schemes.product import ProductSearchFilters

logger = logging.getLogger(__name__)


class ProductRepository:
    def __init__(self, db: DatabaseConnection) -> None:
        self.db = db

    @staticmethod
    def _tokenize(value: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", value.lower())

    def get_by_id(self, product_id: str) -> dict[str, Any] | None:
        query = """
            SELECT *
            FROM products
            WHERE id = %s
            LIMIT 1
        """

        with self.db.connect() as connection:
            row = connection.execute(query, (product_id,)).fetchone()

        return row

    def get_by_code(self, product_code: str) -> dict[str, Any] | None:
        query = """
            SELECT *
            FROM products
            WHERE product_code = %s
            LIMIT 1
        """

        with self.db.connect() as connection:
            row = connection.execute(query, (product_code,)).fetchone()

        return row

    def get_by_name(self, name: str) -> dict[str, Any] | None:
        query = """
            SELECT *
            FROM products
            WHERE LOWER(name) = LOWER(%s)
               OR name ILIKE %s
            ORDER BY
                CASE WHEN LOWER(name) = LOWER(%s) THEN 0 ELSE 1 END,
                brand ASC,
                name ASC,
                product_code ASC
            LIMIT 1
        """

        with self.db.connect() as connection:
            row = connection.execute(
                query,
                (name, f"%{name}%", name),
            ).fetchone()

        return row

    @staticmethod
    def _build_order_by(
        sort_by: str | None = None,
        sort_order: str = "asc",
    ) -> str:
        sort_columns = {
            "price": "usd_price",
            "stock": "stock",
            "ram": "ram",
            "name": "name",
        }

        column = sort_columns.get(sort_by or "", "name")
        direction = "DESC" if sort_order.lower() == "desc" else "ASC"

        return f"""
            ORDER BY
                CASE WHEN {column} IS NULL THEN 1 ELSE 0 END,
                {column} {direction},
                brand ASC,
                name ASC,
                product_code ASC
        """

    def _build_filter_clauses(
        self,
        filters: ProductSearchFilters,
        *,
        min_source_price: float | None = None,
        max_source_price: float | None = None,
    ) -> tuple[list[str], list[Any]]:

        clauses: list[str] = []
        params: list[Any] = []

        # General text search
        if filters.query and filters.query.strip():
            term = f"%{filters.query.strip()}%"

            clauses.append("""
                (
                    product_code ILIKE %s
                    OR brand ILIKE %s
                    OR model ILIKE %s
                    OR name ILIKE %s
                    OR os ILIKE %s
                    OR processor_name ILIKE %s
                    OR processor_brand ILIKE %s
                    OR ram_type ILIKE %s
                    OR display_type ILIKE %s
                    OR gpu ILIKE %s
                    OR gpu_brand ILIKE %s
                    OR battery_life ILIKE %s
                    OR tags ILIKE %s
                )
            """)

            params.extend([term] * 13)

        # Text filters
        string_fields = [
            ("product_code", "product_code ILIKE %s"),
            ("name", "name ILIKE %s"),
            ("model", "model ILIKE %s"),
            ("brand", "brand ILIKE %s"),
            ("os", "os ILIKE %s"),
            ("processor_brand", "processor_brand ILIKE %s"),
            ("ram_type", "ram_type ILIKE %s"),
            ("display_type", "display_type ILIKE %s"),
            ("gpu", "gpu ILIKE %s"),
            ("gpu_brand", "gpu_brand ILIKE %s"),
        ]

        for field_name, clause in string_fields:
            value = getattr(filters, field_name, None)

            if isinstance(value, str) and value.strip():
                clauses.append(clause)
                params.append(f"%{value.strip()}%")

        # Processor name: all tokens must match
        if filters.processor_name and filters.processor_name.strip():
            tokens = self._tokenize(filters.processor_name)

            if tokens:
                clauses.append(
                    "("
                    + " AND ".join(
                        "processor_name ILIKE %s"
                        for _ in tokens
                    )
                    + ")"
                )

                params.extend(f"%{token}%" for token in tokens)

        # Processor speed
        if filters.min_ghz is not None:
            clauses.append("processor_ghz >= %s")
            params.append(filters.min_ghz)

        if filters.max_ghz is not None:
            clauses.append("processor_ghz <= %s")
            params.append(filters.max_ghz)

        # Expandable RAM
        if filters.ram_expandable is not None:
            clauses.append("ram_expandable = %s")
            params.append(filters.ram_expandable)

        # Installed RAM
        if filters.min_ram is not None:
            clauses.append("ram >= %s")
            params.append(filters.min_ram)

        if filters.max_ram is not None:
            clauses.append("ram <= %s")
            params.append(filters.max_ram)

        # Display size
        if filters.min_display is not None:
            clauses.append("display_inch >= %s")
            params.append(filters.min_display)

        if filters.max_display is not None:
            clauses.append("display_inch <= %s")
            params.append(filters.max_display)

        # SSD capacity
        if filters.min_ssd is not None:
            clauses.append("ssd_gb >= %s")
            params.append(filters.min_ssd)

        if filters.max_ssd is not None:
            clauses.append("ssd_gb <= %s")
            params.append(filters.max_ssd)

        # HDD capacity
        if filters.min_hdd is not None:
            clauses.append("hdd_gb >= %s")
            params.append(filters.min_hdd)

        if filters.max_hdd is not None:
            clauses.append("hdd_gb <= %s")
            params.append(filters.max_hdd)

        # Price (USD)
        min_price = (
            min_source_price
            if min_source_price is not None
            else filters.min_price
        )

        max_price = (
            max_source_price
            if max_source_price is not None
            else filters.max_price
        )

        if min_price is not None:
            clauses.append("usd_price >= %s")
            params.append(min_price)

        if max_price is not None:
            clauses.append("usd_price <= %s")
            params.append(max_price)

        # Inventory
        if filters.min_stock is not None:
            clauses.append("stock >= %s")
            params.append(filters.min_stock)

        if filters.max_stock is not None:
            clauses.append("stock <= %s")
            params.append(filters.max_stock)

        return clauses, params

    def search(
        self,
        filters: ProductSearchFilters,
        *,
        min_source_price: float | None = None,
        max_source_price: float | None = None,
    ) -> list[dict[str, Any]]:

        clauses, params = self._build_filter_clauses(
            filters,
            min_source_price=min_source_price,
            max_source_price=max_source_price,
        )

        where_sql = (
            f"WHERE {' AND '.join(clauses)}"
            if clauses
            else ""
        )

        order_sql = self._build_order_by(
            filters.sort_by,
            filters.sort_order,
        )

        query = f"""
            SELECT *
            FROM products
            {where_sql}
            {order_sql}
            LIMIT %s
        """

        params.append(filters.limit)

        self._log_query(
            operation="search",
            query=query,
            params=params,
        )

        with self.db.connect() as connection:
            rows = connection.execute(query, params).fetchall()

        return rows

    def get_total_stock(
        self,
        filters: ProductSearchFilters,
        *,
        min_source_price: float | None = None,
        max_source_price: float | None = None,
    ) -> int:

        clauses, params = self._build_filter_clauses(
            filters,
            min_source_price=min_source_price,
            max_source_price=max_source_price,
        )

        where_sql = (
            f"WHERE {' AND '.join(clauses)}"
            if clauses
            else ""
        )

        query = f"""
            SELECT COALESCE(SUM(stock), 0) AS total_stock
            FROM products
            {where_sql}
        """

        with self.db.connect() as connection:
            row = connection.execute(query, params).fetchone()

        return int(row["total_stock"]) if row else 0

    def insert(self, product: dict[str, Any]) -> dict[str, Any]:
        generated_id = product.get("id") or str(uuid.uuid4())

        query = """
            INSERT INTO products (
                id,
                product_code,
                brand,
                model,
                name,
                os,
                usd_price,
                processor_name,
                processor_brand,
                ram_expandable,
                ram,
                ram_type,
                processor_ghz,
                display_type,
                display_inch,
                gpu,
                gpu_brand,
                ssd_gb,
                hdd_gb,
                battery_life,
                tags,
                stock
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING *
        """

        params = (
            generated_id,
            product["product_code"],
            product["brand"],
            product.get("model"),
            product["name"],
            product.get("os"),
            product.get("usd_price"),
            product.get("processor_name"),
            product.get("processor_brand"),
            product.get("ram_expandable", 0),
            product.get("ram"),
            product.get("ram_type"),
            product.get("processor_ghz"),
            product.get("display_type"),
            product.get("display_inch"),
            product.get("gpu"),
            product.get("gpu_brand"),
            product.get("ssd_gb"),
            product.get("hdd_gb"),
            product.get("battery_life"),
            product.get("tags"),
            product.get("stock", 0),
        )

        with self.db.connect() as connection:
            row = connection.execute(query, params).fetchone()

        if row is None:
            raise RuntimeError(
                f"Failed to retrieve inserted product: {generated_id}"
            )

        return row

    def get_all(self) -> list[Product]:
        query = """
            SELECT *
            FROM products
            ORDER BY name ASC
        """

        with self.db.connect() as connection:
            rows = connection.execute(query).fetchall()

        return [
            Product.from_row(row)
            for row in rows
        ]

    def upsert_many(self, products: list[dict[str, Any]]) -> int:
        if not products:
            return 0

        query = """
            INSERT INTO products (
                id,
                product_code,
                brand,
                model,
                name,
                os,
                usd_price,
                processor_name,
                processor_brand,
                ram_expandable,
                ram,
                ram_type,
                processor_ghz,
                display_type,
                display_inch,
                gpu,
                gpu_brand,
                ssd_gb,
                hdd_gb,
                battery_life,
                tags,
                stock
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (product_code) DO UPDATE SET
                brand = EXCLUDED.brand,
                model = EXCLUDED.model,
                name = EXCLUDED.name,
                os = EXCLUDED.os,
                usd_price = EXCLUDED.usd_price,
                processor_name = EXCLUDED.processor_name,
                processor_brand = EXCLUDED.processor_brand,
                ram_expandable = EXCLUDED.ram_expandable,
                ram = EXCLUDED.ram,
                ram_type = EXCLUDED.ram_type,
                processor_ghz = EXCLUDED.processor_ghz,
                display_type = EXCLUDED.display_type,
                display_inch = EXCLUDED.display_inch,
                gpu = EXCLUDED.gpu,
                gpu_brand = EXCLUDED.gpu_brand,
                ssd_gb = EXCLUDED.ssd_gb,
                hdd_gb = EXCLUDED.hdd_gb,
                battery_life = EXCLUDED.battery_life,
                tags = EXCLUDED.tags,
                stock = EXCLUDED.stock,
                updated_at = CURRENT_TIMESTAMP
        """

        params = [
            (
                product.get("id") or str(uuid.uuid4()),
                product["product_code"],
                product["brand"],
                product.get("model"),
                product["name"],
                product.get("os"),
                product.get("usd_price"),
                product.get("processor_name"),
                product.get("processor_brand"),
                product.get("ram_expandable", 0),
                product.get("ram"),
                product.get("ram_type"),
                product.get("processor_ghz"),
                product.get("display_type"),
                product.get("display_inch"),
                product.get("gpu"),
                product.get("gpu_brand"),
                product.get("ssd_gb"),
                product.get("hdd_gb"),
                product.get("battery_life"),
                product.get("tags"),
                product.get("stock", 0),
            )
            for product in products
        ]

        with self.db.connect() as connection:
            connection.executemany(query, params)

        return len(params)

    def _log_query(
        self,
        operation: str,
        query: str,
        params: tuple[Any, ...] | list[Any] = (),
    ) -> None:
        logger.info(
            "Database query | operation=%s | SQL: %s | Parameters: %s",
            operation,
            " ".join(query.split()),
            params,
        )
