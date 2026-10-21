from __future__ import annotations

from app.schemes.product import ProductSearchFilters


def _ram_amount(value: str | None) -> float:
    assert value is not None
    return float(value.split()[0])


def test_product_search_still_returns_converted_price(client):
    response = client.get("/products/search", params={"name": "VivoBook"})

    assert response.status_code == 200
    products = response.json()
    assert len(products) >= 2

    first = next(item for item in products if item["product_code"] == "ASUS-VIVO-8")
    assert first["currency"] == "IDR"
    assert first["price"] == 190000.0


def test_min_ram_filter_includes_products_at_or_above_threshold(product_service):
    results = product_service.search_products(ProductSearchFilters(min_ram=16, limit=100))

    assert results
    assert all(product.ram_gb >= 16 for product in results if product.ram_gb is not None)


def test_intel_core_i7_matching_excludes_other_intel_processors(product_service):
    results = product_service.search_products(
        ProductSearchFilters(processor_name="Intel Core i7", limit=100)
    )

    assert results
    assert all("i7" in (product.processor_name or "").lower() for product in results)
    assert all("i5" not in (product.processor_name or "").lower() for product in results)
    assert all("i9" not in (product.processor_name or "").lower() for product in results)


def test_search_sorts_by_price_ascending(product_service):
    results = product_service.search_products(
        ProductSearchFilters(min_ram=16, sort_by="price", sort_order="asc", limit=100)
    )

    prices = [product.price for product in results]
    assert prices == sorted(prices)


def test_combined_filters_apply_before_limit(product_service, db_service):
    with db_service.connect() as connection:
        expected = connection.execute(
            """
            SELECT product_code
            FROM products
            WHERE ram_gb >= ?
              AND LOWER(processor_name) LIKE ?
            ORDER BY price ASC, brand, name
            LIMIT 1
            """,
            (16, "%i7%"),
        ).fetchone()

    results = product_service.search_products(
        ProductSearchFilters(
            processor_name="Intel Core i7",
            min_ram=16,
            sort_by="price",
            sort_order="asc",
            limit=1,
        )
    )

    assert len(results) == 1
    assert expected is not None
    assert results[0].product_code == expected[0]


def test_search_returns_empty_results_for_impossible_filters(product_service):
    results = product_service.search_products(
        ProductSearchFilters(
            processor_name="Intel Core i7",
            min_ram=64,
            limit=20,
        )
    )

    assert results == []
