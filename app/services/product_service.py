from __future__ import annotations

import re

from app.configs.config import get_settings
from app.database.repositories.product_repository import ProductRepository
from app.models.product import Product
from app.schemes.product_search import ProductSearchFilters



class ProductService:
    def __init__(
        self,
        repository: ProductRepository | None = None,
    ) -> None:
        settings = get_settings()

        self.repository = repository or ProductRepository()
        self.source_currency = settings.price_source_currency.upper()
        self.target_currency = settings.price_target_currency.upper()
        self.conversion_rate = settings.price_conversion_rate

    def _convert_source_to_target(
        self,
        price: float | None,
    ) -> float | None:
        if price is None:
            return None

        return round(price * self.conversion_rate, 2)

    def _convert_target_to_source(
        self,
        price: float | None,
    ) -> float | None:
        if price is None or self.conversion_rate == 0:
            return None

        return round(price / self.conversion_rate, 2)

    def _normalize_product_prices(self, product: Product) -> Product:
        return product.model_copy(
            update={
                "price": self._convert_source_to_target(product.price),
                "currency": self.target_currency,
            }
        )

    @staticmethod
    def _tokenize(value: str) -> list[str]:
        return [
            token
            for token in re.findall(r"[a-z0-9]+", value.lower())
            if token
        ]

    def get_product_details(self, sku_or_name: str) -> Product | None:
        identifier = sku_or_name.strip()

        if not identifier:
            return None

        row = self.repository.get_by_product_code(identifier)

        if row is None:
            row = self.repository.get_by_name(identifier)

        if row is None:
            return None

        return self._normalize_product_prices(Product.from_row(row))

    def search_products(
        self,
        filters: ProductSearchFilters | None = None,
    ) -> list[Product]:
        filters = filters or ProductSearchFilters()

        rows = self.repository.search(filters)

        return [
            self._normalize_product_prices(Product.from_row(row))
            for row in rows
        ]

    def get_product_stock(self, sku_or_name: str) -> int | None:
        product = self.get_product_details(sku_or_name)
        return product.stock if product else None

    def get_product_price(self, sku_or_name: str) -> float | None:
        product = self.get_product_details(sku_or_name)
        return product.price if product else None

    def get_total_stock(
        self,
        filters: ProductSearchFilters | None = None,
    ) -> int:
        return self.repository.get_total_stock(
            filters or ProductSearchFilters()
        )