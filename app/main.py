from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel

from app.models import Product, ProductSearchFilters
from app.product_service import ProductService


app = FastAPI(
    title="Product Service API",
    version="1.0.0",
    description="API for product lookup, search, stock, and price retrieval.",
)


class StockResponse(BaseModel):
    sku_or_name: str
    stock: int
    product: Product


class PriceResponse(BaseModel):
    sku_or_name: str
    price: float | None
    product: Product


@lru_cache(maxsize=1)
def get_product_service() -> ProductService:
    return ProductService()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/products/details", response_model=Product)
def get_product_details(
    sku_or_name: str = Query(..., description="Product SKU or product name"),
    service: ProductService = Depends(get_product_service),
) -> Product:
    product = service.get_product_details(sku_or_name)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@app.get("/products/search", response_model=list[Product])
def search_products(
    query: str | None = Query(default=None, description="General search keyword"),
    sku: str | None = Query(default=None),
    name: str | None = Query(default=None),
    category: str | None = Query(default=None),
    brand: str | None = Query(default=None),
    processor_brand: str | None = Query(default=None),
    processor_name: str | None = Query(default=None),
    ram: str | None = Query(default=None),
    display_type: str | None = Query(default=None),
    ram_type: str | None = Query(default=None),
    gpu_brand: str | None = Query(default=None),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    min_stock: int | None = Query(default=None, ge=0),
    max_stock: int | None = Query(default=None, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    service: ProductService = Depends(get_product_service),
) -> list[Product]:
    filters = ProductSearchFilters(
        query=query,
        sku=sku,
        name=name,
        category=category,
        brand=brand,
        processor_brand=processor_brand,
        processor_name=processor_name,
        ram=ram,
        display_type=display_type,
        ram_type=ram_type,
        gpu_brand=gpu_brand,
        min_price=min_price,
        max_price=max_price,
        min_stock=min_stock,
        max_stock=max_stock,
        limit=limit,
    )
    return service.search_products(filters)


@app.get("/products/stock", response_model=StockResponse)
def get_product_stock(
    sku_or_name: str = Query(..., description="Product SKU or product name"),
    service: ProductService = Depends(get_product_service),
) -> StockResponse:
    product = service.get_product_details(sku_or_name)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    stock = service.get_product_stock(sku_or_name)
    return StockResponse(sku_or_name=sku_or_name, stock=stock or 0, product=product)


@app.get("/products/price", response_model=PriceResponse)
def get_product_price(
    sku_or_name: str = Query(..., description="Product SKU or product name"),
    service: ProductService = Depends(get_product_service),
) -> PriceResponse:
    product = service.get_product_details(sku_or_name)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    price = service.get_product_price(sku_or_name)
    return PriceResponse(sku_or_name=sku_or_name, price=price, product=product)
