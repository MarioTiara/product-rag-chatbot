from __future__ import annotations

from typing import Any

from app.database import DatabaseService
from app.config import get_settings
from app.models import Product, ProductSearchFilters


class ProductService:
    def __init__(self, database: DatabaseService | None = None) -> None:
        settings = get_settings()
        self.database = database or DatabaseService()
        self.database.initialize()
        self.source_currency = settings.price_source_currency.upper()
        self.target_currency = settings.price_target_currency.upper()
        self.conversion_rate = settings.price_conversion_rate

    def _convert_source_to_target(self, price: float | None) -> float | None:
        if price is None:
            return None
        return round(price * self.conversion_rate, 2)

    def _convert_target_to_source(self, price: float | None) -> float | None:
        if price is None:
            return None
        if self.conversion_rate == 0:
            return None
        return round(price / self.conversion_rate, 2)

    def _normalize_product_prices(self, product: Product) -> Product:
        return product.model_copy(
            update={
                "price": self._convert_source_to_target(product.price),
                "currency": self.target_currency,
            }
        )

    def get_product_details(self, sku_or_name: str) -> Product | None:
        identifier = sku_or_name.strip()
        if not identifier:
            return None

        row = self.database.get_product_by_sku(identifier)
        if row:
            return self._normalize_product_prices(Product.from_row(row))

        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                SELECT *
                FROM products
                WHERE LOWER(name) = LOWER(?)
                   OR LOWER(name) LIKE LOWER(?)
                ORDER BY
                    CASE WHEN LOWER(name) = LOWER(?) THEN 0 ELSE 1 END,
                    brand,
                    name
                LIMIT 1
                """,
                (identifier, f"%{identifier}%", identifier),
            )
            row = cursor.fetchone()
            return self._normalize_product_prices(Product.from_row(dict(row))) if row else None

    def _build_filter_clauses(self, filters: ProductSearchFilters) -> tuple[list[str], list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []

        if filters.query:
            term = f"%{filters.query.strip()}%"
            clauses.append("(sku LIKE ? OR brand LIKE ? OR name LIKE ? OR category LIKE ?)")
            params.extend([term, term, term, term])

        string_fields = [
            ("sku", "sku LIKE ?"),
            ("name", "LOWER(name) LIKE LOWER(?)"),
            ("category", "LOWER(category) LIKE LOWER(?)"),
            ("brand", "LOWER(brand) LIKE LOWER(?)"),
            ("processor_brand", "LOWER(processor_brand) LIKE LOWER(?)"),
            ("processor_name", "LOWER(processor_name) LIKE LOWER(?)"),
            ("ram_expandable", "LOWER(ram_expandable) LIKE LOWER(?)"),
            ("ram", "LOWER(ram) LIKE LOWER(?)"),
            ("ram_type", "LOWER(ram_type) LIKE LOWER(?)"),
            ("ghz", "LOWER(ghz) LIKE LOWER(?)"),
            ("display_type", "LOWER(display_type) LIKE LOWER(?)"),
            ("display", "LOWER(display) LIKE LOWER(?)"),
            ("gpu", "LOWER(gpu) LIKE LOWER(?)"),
            ("gpu_brand", "LOWER(gpu_brand) LIKE LOWER(?)"),
            ("ssd", "LOWER(ssd) LIKE LOWER(?)"),
            ("hdd", "LOWER(hdd) LIKE LOWER(?)"),
            ("battery_life", "LOWER(battery_life) LIKE LOWER(?)"),
        ]

        for field_name, clause in string_fields:
            value = getattr(filters, field_name)
            if value:
                clauses.append(clause)
                cleaned = value.strip()
                params.append(f"%{cleaned}%")

        if filters.min_price is not None:
            clauses.append("price >= ?")
            params.append(self._convert_target_to_source(filters.min_price))

        if filters.max_price is not None:
            clauses.append("price <= ?")
            params.append(self._convert_target_to_source(filters.max_price))

        if filters.min_stock is not None:
            clauses.append("stock >= ?")
            params.append(filters.min_stock)

        if filters.max_stock is not None:
            clauses.append("stock <= ?")
            params.append(filters.max_stock)

        return clauses, params

    def search_products(self, filters: ProductSearchFilters | None = None) -> list[Product]:
        filters = filters or ProductSearchFilters()
        clauses, params = self._build_filter_clauses(filters)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(filters.limit)

        with self.database.connection() as connection:
            cursor = connection.execute(
                f"""
                SELECT *
                FROM products
                {where_sql}
                ORDER BY brand, name
                LIMIT ?
                """,
                params,
            )
            return [self._normalize_product_prices(Product.from_row(dict(row))) for row in cursor.fetchall()]

    def get_product_stock(self, sku_or_name: str) -> int | None:
        product = self.get_product_details(sku_or_name)
        return product.stock if product else None

    def get_product_price(self, sku_or_name: str) -> float | None:
        product = self.get_product_details(sku_or_name)
        return product.price if product else None

    def get_total_stock(self, filters: ProductSearchFilters | None = None) -> int:
        filters = filters or ProductSearchFilters()
        clauses, params = self._build_filter_clauses(filters)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.database.connection() as connection:
            cursor = connection.execute(
                f"""
                SELECT COALESCE(SUM(stock), 0) AS total_stock
                FROM products
                {where_sql}
                """,
                params,
            )
            row = cursor.fetchone()
            return int(row["total_stock"] if row else 0)
