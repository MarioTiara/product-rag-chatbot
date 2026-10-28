
from __future__ import annotations

import logging
import re
from typing import Any
import uuid

from app.database.connection import DatabaseConnection
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
            WHERE id = ?
            LIMIT 1
        """

        with self.db.connect() as connection:
            row = connection.execute(query, (product_id,)).fetchone()

        return dict(row) if row else None

    def get_by_code(self, product_code: str) -> dict[str, Any] | None:
        query = """
            SELECT *
            FROM products
            WHERE product_code = ?
            LIMIT 1
        """

        with self.db.connect() as connection:
            row = connection.execute(query, (product_code,)).fetchone()

        return dict(row) if row else None

    def get_by_name(self, name: str) -> dict[str, Any] | None:
        query = """
            SELECT *
            FROM products
            WHERE LOWER(name) = LOWER(?)
               OR LOWER(name) LIKE LOWER(?)
            ORDER BY
                CASE WHEN LOWER(name) = LOWER(?) THEN 0 ELSE 1 END,
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

        return dict(row) if row else None
    
    @staticmethod
    def _build_order_by(
        sort_by: str | None,
        sort_order: str,
    ) -> str:
        allowed_columns = {
            "price": "price",
            "stock": "stock",
            "ram": "ram_gb",
            "name": "name",
        }

        column = allowed_columns.get(sort_by or "", "brand")

        direction = "DESC" if sort_order == "desc" else "ASC"

        if column == "price":
            return f"""
                ORDER BY
                    CASE WHEN price IS NULL THEN 1 ELSE 0 END,
                    price {direction},
                    brand ASC,
                    name ASC,
                    product_code ASC
            """

        return f"""
            ORDER BY
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
            clauses.append(
                """
                (
                    product_code LIKE ?
                    OR product_id LIKE ?
                    OR brand LIKE ?
                    OR model LIKE ?
                    OR name LIKE ?
                    OR os LIKE ?
                    OR processor_name LIKE ?
                    OR processor_brand LIKE ?
                    OR ram_type LIKE ?
                    OR display_type LIKE ?
                    OR gpu LIKE ?
                    OR gpu_brand LIKE ?
                    OR battery_life LIKE ?
                    OR tags LIKE ?
                )
                """
            )
            params.extend([term] * 14)

        # Text filters
        string_fields = [
            ("product_code", "product_code LIKE ?"),
            ("name", "LOWER(name) LIKE LOWER(?)"),
            ("model", "LOWER(model) LIKE LOWER(?)"),
            ("brand", "LOWER(brand) LIKE LOWER(?)"),
            ("os", "LOWER(os) LIKE LOWER(?)"),
            ("processor_brand", "LOWER(processor_brand) LIKE LOWER(?)"),
            ("ram_type", "LOWER(ram_type) LIKE LOWER(?)"),
            ("display_type", "LOWER(display_type) LIKE LOWER(?)"),
            ("gpu", "LOWER(gpu) LIKE LOWER(?)"),
            ("gpu_brand", "LOWER(gpu_brand) LIKE LOWER(?)"),
        ]

        for field_name, clause in string_fields:
            value = getattr(filters, field_name)

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
                        "LOWER(processor_name) LIKE ?"
                        for _ in tokens
                    )
                    + ")"
                )
                params.extend(f"%{token}%" for token in tokens)

        # Processor speed
        if filters.min_ghz is not None:
            clauses.append("processor_ghz >= ?")
            params.append(filters.min_ghz)

        if filters.max_ghz is not None:
            clauses.append("processor_ghz <= ?")
            params.append(filters.max_ghz)

        # Expandable RAM capacity
        if filters.ram_expandable is not None:
            clauses.append("ram_expandable = ?")
            params.append(filters.ram_expandable)

        # Installed RAM
        if filters.min_ram is not None:
            clauses.append("ram_gb >= ?")
            params.append(filters.min_ram)

        if filters.max_ram is not None:
            clauses.append("ram_gb <= ?")
            params.append(filters.max_ram)

        # Display size
        if filters.min_display is not None:
            clauses.append("display_inch >= ?")
            params.append(filters.min_display)

        if filters.max_display is not None:
            clauses.append("display_inch <= ?")
            params.append(filters.max_display)

        # SSD capacity
        if filters.min_ssd is not None:
            clauses.append("ssd_gb >= ?")
            params.append(filters.min_ssd)

        if filters.max_ssd is not None:
            clauses.append("ssd_gb <= ?")
            params.append(filters.max_ssd)

        # HDD capacity
        if filters.min_hdd is not None:
            clauses.append("hdd_gb >= ?")
            params.append(filters.min_hdd)

        if filters.max_hdd is not None:
            clauses.append("hdd_gb <= ?")
            params.append(filters.max_hdd)

        # Price: use converted source-currency values when provided
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
            clauses.append("price >= ?")
            params.append(min_price)

        if max_price is not None:
            clauses.append("price <= ?")
            params.append(max_price)

        # Inventory
        if filters.min_stock is not None:
            clauses.append("stock >= ?")
            params.append(filters.min_stock)

        if filters.max_stock is not None:
            clauses.append("stock <= ?")
            params.append(filters.max_stock)

        return clauses, params

    @staticmethod
    def _build_order_by(
        sort_by: str = "name",
        sort_order: str = "asc",
    ) -> str:
        sort_columns = {
            "price": "price",
            "stock": "stock",
            "ram": "ram_gb",
            "name": "name",
        }

        column = sort_columns.get(sort_by, "name")
        direction = "DESC" if sort_order.lower() == "desc" else "ASC"

        if column == "price":
            return f"""
                ORDER BY
                    CASE WHEN price IS NULL THEN 1 ELSE 0 END,
                    price {direction},
                    brand ASC,
                    name ASC,
                    product_code ASC
            """

        return f"""
            ORDER BY
                CASE WHEN {column} IS NULL THEN 1 ELSE 0 END,
                {column} {direction},
                brand ASC,
                name ASC,
                product_code ASC
        """

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
            LIMIT ?
        """

        params.append(filters.limit)

        # Log final SQL and parameters
        self._log_query(
            operation="search",
            query=query,
            params=params,
        )

        with self.db.connect() as connection:
            rows = connection.execute(query, params).fetchall()

        return [dict(row) for row in rows]

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
        product_id = product.get("id") or str(uuid.uuid4())

        query = """ 
            INSERT INTO products (
                id,
                product_id,
                brand,
                model,
                product_code,
                name,
                os,
                price,
                processor_name,
                processor_brand,
                ram_expandable,
                ram_gb,
                ram_type,
                processor_ghz,
                display_type,
                display_inch,
                gpu,
                gpu_brand,
                ssd_gb,
                hdd_gb,
                stock,
                battery_life,
                tags
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?
            )
        """

        params = (
            product_id,
            product.get("product_id"),
            product["brand"],
            product.get("model"),
            product["product_code"],
            product["name"],
            product.get("os"),
            product.get("price"),
            product.get("processor_name"),
            product.get("processor_brand"),
            product.get("ram_expandable", 0),
            product.get("ram_gb"),
            product.get("ram_type"),
            product.get("processor_ghz"),
            product.get("display_type"),
            product.get("display_inch"),
            product.get("gpu"),
            product.get("gpu_brand"),
            product.get("ssd_gb"),
            product.get("hdd_gb"),
            product.get("stock", 0),
            product.get("battery_life"),
            product.get("tags"),
        )

        with self.db.connect() as connection:
            connection.execute(query, params)

            row = connection.execute(
                "SELECT * FROM products WHERE id = ?",
                (product_id,),
            ).fetchone()

        if row is None:
            raise RuntimeError(
                f"Failed to retrieve inserted product: {product_id}"
            )

        return dict(row)

    def upsert_many(self, products: list[dict[str, Any]]) -> int:
        if not products:
            return 0

        query = """
            INSERT INTO products (
                id, product_id, brand, model, product_code, name, os,
                price, processor_name, processor_brand, ram_expandable,
                ram_gb, ram_type, processor_ghz, display_type, display_inch,
                gpu, gpu_brand, ssd_gb, hdd_gb, stock, battery_life, tags
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(product_code) DO UPDATE SET
                product_id = excluded.product_id,
                brand = excluded.brand,
                model = excluded.model,
                name = excluded.name,
                os = excluded.os,
                price = excluded.price,
                processor_name = excluded.processor_name,
                processor_brand = excluded.processor_brand,
                ram_expandable = excluded.ram_expandable,
                ram_gb = excluded.ram_gb,
                ram_type = excluded.ram_type,
                processor_ghz = excluded.processor_ghz,
                display_type = excluded.display_type,
                display_inch = excluded.display_inch,
                gpu = excluded.gpu,
                gpu_brand = excluded.gpu_brand,
                ssd_gb = excluded.ssd_gb,
                hdd_gb = excluded.hdd_gb,
                stock = excluded.stock,
                battery_life = excluded.battery_life,
                tags = excluded.tags,
                updated_at = CURRENT_TIMESTAMP
        """

        params = [
            (
                product.get("id") or str(uuid.uuid4()),
                product.get("product_id"),
                product["brand"],
                product.get("model"),
                product["product_code"],
                product["name"],
                product.get("os"),
                product.get("price"),
                product.get("processor_name"),
                product.get("processor_brand"),
                product.get("ram_expandable", 0),
                product.get("ram_gb"),
                product.get("ram_type"),
                product.get("processor_ghz"),
                product.get("display_type"),
                product.get("display_inch"),
                product.get("gpu"),
                product.get("gpu_brand"),
                product.get("ssd_gb"),
                product.get("hdd_gb"),
                product.get("stock", 0),
                product.get("battery_life"),
                product.get("tags"),
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