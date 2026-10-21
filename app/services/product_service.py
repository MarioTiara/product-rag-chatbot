from __future__ import annotations

from app.configs.config import get_settings
from app.database.repositories.product_repository import ProductRepository
from app.models.product import Product
from app.schemes.product import ProductSearchFilters


class ProductService:
    def __init__(
        self,
        repository: ProductRepository | None = None,
    ) -> None:
        settings = get_settings()

        self.repository = repository or ProductRepository()
        self.target_currency = settings.price_target_currency.upper()
        self.conversion_rate = settings.price_conversion_rate

    def _convert_source_to_target(
        self,
        price: float | None,
    ) -> float | None:
        if price is None:
            return None

        return round(price * self.conversion_rate, 2)

    def _normalize_product_prices(
        self,
        product: Product,
    ) -> Product:
        return product.model_copy(
            update={
                "price": self._convert_source_to_target(product.price),
                "currency": self.target_currency,
            }
        )

    def get_product_details(
        self,
        name: str,
    ) -> Product | None:
        name = name.strip()

        if not name:
            return None

        row = self.repository.get_by_name(name)

        if row is None:
            return None

        return self._normalize_product_prices(
            Product.from_row(row)
        )

    def search_products(
        self,
        filters: ProductSearchFilters | None = None,
    ) -> list[Product]:
        filters = filters or ProductSearchFilters()

        rows = self.repository.search(filters)

        return [
            self._normalize_product_prices(
                Product.from_row(row)
            )
            for row in rows
        ]

    def check_product_availability(
        self,
        name: str,
    ) -> dict | None:
        product = self.get_product_details(name)

        if product is None:
            return None

        stock = product.stock or 0

        return {
            "product_name": product.name,
            "available": stock > 0,
            "stock": stock,
        }

    def get_total_stock(
        self,
        filters: ProductSearchFilters | None = None,
    ) -> int:
        return self.repository.get_total_stock(
            filters or ProductSearchFilters()
        )
