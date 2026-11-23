
from __future__ import annotations

from app.core.configs.config import get_settings
from app.database.repositories.postgres.product_repository import ProductRepository
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

    # =====================================================
    # Price Conversion
    # =====================================================

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

    # =====================================================
    # Product Details
    # =====================================================

    def get_product_details(
        self,
        name: str,
    ) -> Product | None:
        name = name.strip()

        if not name:
            return None

        product = self.repository.get_by_name(name)

        if product is None:
            return None

        return self._normalize_product_prices(product)

    # =====================================================
    # Product Search
    # =====================================================

    def search_products(
        self,
        filters: ProductSearchFilters | None = None,
    ) -> list[Product]:
        filters = filters or ProductSearchFilters()

        products = self.repository.search(filters)

        return [
            self._normalize_product_prices(product)
            for product in products
        ]

    # =====================================================
    # Product Availability
    # =====================================================

    def check_product_availability(
        self,
        name: str,
    ) -> dict[str, str | bool | int] | None:
        product = self.get_product_details(name)

        if product is None:
            return None

        stock = product.stock

        return {
            "product_name": product.name,
            "available": stock > 0,
            "stock": stock,
        }

    # =====================================================
    # Inventory
    # =====================================================

    def get_total_stock(
        self,
        filters: ProductSearchFilters | None = None,
    ) -> int:
        return self.repository.get_total_stock(
            filters or ProductSearchFilters()
        )
