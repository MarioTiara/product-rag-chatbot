from __future__ import annotations

from typing import Any

from app.database import DatabaseService
from app.models import Product, ProductSearchFilters


class ProductService:
    def __init__(self, database: DatabaseService | None = None) -> None:
        self.database = database or DatabaseService()
        self.database.initialize()

    def get_product_details(self, sku_or_name: str) -> Product | None:
        identifier = sku_or_name.strip()
        if not identifier:
            return None

        row = self.database.get_product_by_sku(identifier)
        if row:
            return Product.from_row(row)

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
            return Product.from_row(dict(row)) if row else None

    def search_products(self, filters: ProductSearchFilters | None = None) -> list[Product]:
        filters = filters or ProductSearchFilters()
        clauses: list[str] = []
        params: list[Any] = []

        if filters.query:
            term = f"%{filters.query.strip()}%"
            clauses.append("(sku LIKE ? OR brand LIKE ? OR name LIKE ? OR category LIKE ?)")
            params.extend([term, term, term, term])

        if filters.sku:
            clauses.append("sku LIKE ?")
            params.append(f"%{filters.sku.strip()}%")

        if filters.name:
            clauses.append("name LIKE ?")
            params.append(f"%{filters.name.strip()}%")

        if filters.category:
            clauses.append("LOWER(category) LIKE LOWER(?)")
            params.append(f"%{filters.category.strip()}%")

        if filters.brand:
            clauses.append("LOWER(brand) LIKE LOWER(?)")
            params.append(f"%{filters.brand.strip()}%")

        if filters.processor_brand:
            clauses.append("LOWER(processor_brand) LIKE LOWER(?)")
            params.append(f"%{filters.processor_brand.strip()}%")

        if filters.processor_name:
            clauses.append("LOWER(processor_name) LIKE LOWER(?)")
            params.append(f"%{filters.processor_name.strip()}%")

        if filters.ram:
            clauses.append("LOWER(ram) LIKE LOWER(?)")
            params.append(f"%{filters.ram.strip()}%")
        
        if filters.display_type:
                clauses.append("LOWER(display_type) LIKE LOWER(?)")
                params.append(f"%{filters.display_type.strip()}%")

        if filters.ram_type:
            clauses.append("LOWER(ram_type) LIKE LOWER(?)")
            params.append(f"%{filters.ram_type.strip()}%")

        if filters.gpu_brand:
            clauses.append("LOWER(gpu_brand) LIKE LOWER(?)")
            params.append(f"%{filters.gpu_brand.strip()}%")

        if filters.min_price is not None:
            clauses.append("price >= ?")
            params.append(filters.min_price)

        if filters.max_price is not None:
            clauses.append("price <= ?")
            params.append(filters.max_price)

        if filters.min_stock is not None:
            clauses.append("stock >= ?")
            params.append(filters.min_stock)

        if filters.max_stock is not None:
            clauses.append("stock <= ?")
            params.append(filters.max_stock)

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
            return [Product.from_row(dict(row)) for row in cursor.fetchall()]

    def get_product_stock(self, sku_or_name: str) -> int | None:
        product = self.get_product_details(sku_or_name)
        return product.stock if product else None

    def get_product_price(self, sku_or_name: str) -> float | None:
        product = self.get_product_details(sku_or_name)
        return product.price if product else None
