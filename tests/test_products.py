from __future__ import annotations

from app.models import ProductSearchFilters


def _ram_amount(value: str | None) -> float:
    assert value is not None
    return float(value.split()[0])


def test_product_search_still_returns_converted_price(client):
    response = client.get("/products/search", params={"name": "VivoBook"})

    assert response.status_code == 200
    products = response.json()
    assert len(products) >= 2

    first = next(item for item in products if item["sku"] == "ASUS-VIVO-8")
    assert first["currency"] == "IDR"
    assert first["price"] == 190000.0


def test_min_ram_filter_includes_products_at_or_above_threshold(product_service):
    results = product_service.search_products(ProductSearchFilters(min_ram=16, limit=100))

    assert results
    assert all(_ram_amount(product.ram) >= 16 for product in results)


def test_intel_core_i7_matching_excludes_other_intel_processors(product_service):
    results = product_service.search_products(
        ProductSearchFilters(processor_name="Intel Core i7", limit=100)
    )

    assert results
    assert all("i7" in (product.processor_name or "").lower() for product in results)
    assert all("i5" not in (product.processor_name or "").lower() for product in results)
    assert all("i9" not in (product.processor_name or "").lower() for product in results)


def test_search_sorts_by_price_ascending(product_service):
    results = product_service.search_products(ProductSearchFilters(min_ram=16, price_sort="asc", limit=100))

    prices = [product.price for product in results]
    assert prices == sorted(prices)


def test_combined_filters_apply_before_limit(product_service, db_service):
    with db_service.connection() as connection:
        expected = connection.execute(
            """
            SELECT sku
            FROM products
            WHERE CAST(ram AS REAL) >= ?
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
            price_sort="asc",
            limit=1,
        )
    )

    assert len(results) == 1
    assert expected is not None
    assert results[0].sku == expected[0]


def test_search_returns_empty_results_for_impossible_filters(product_service):
    results = product_service.search_products(
        ProductSearchFilters(
            processor_name="Intel Core i7",
            min_ram=64,
            limit=20,
        )
    )

    assert results == []
