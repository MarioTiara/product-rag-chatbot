from __future__ import annotations


def test_product_search_still_returns_converted_price(client):
    response = client.get("/products/search", params={"name": "VivoBook"})

    assert response.status_code == 200
    products = response.json()
    assert len(products) >= 2

    first = next(item for item in products if item["sku"] == "ASUS-VIVO-8")
    assert first["currency"] == "IDR"
    assert first["price"] == 190000.0
