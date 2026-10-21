from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query


from app.api.dependencies import get_current_user, get_product_service
from app.models.product import Product
from app.schemes.stock import PriceResponse, StockResponse
from app.services.product_service import ProductService
from app.schemes.product import ProductSearchFilters

router = APIRouter(
    prefix="/products",
    tags=["Products"],
    dependencies=[Depends(get_current_user)],
)





@router.get("/details", response_model=Product)
def get_product_details(
    product_code_or_name: str = Query(
        ...,
        description="Product code or product name",
    ),
    service: ProductService = Depends(get_product_service),
) -> Product:
    product = service.get_product_details(product_code_or_name)

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    return product



@router.get("/search", response_model=list[Product])
def search_products(
    filters: Annotated[ProductSearchFilters, Depends()],
    service: ProductService = Depends(get_product_service),
) -> list[Product]:
    return service.search_products(filters)


@router.get("/stock", response_model=StockResponse)
def get_product_stock(
    product_code_or_name: str = Query(...),
    service: ProductService = Depends(get_product_service),
) -> StockResponse:
    product = service.get_product_details(product_code_or_name)

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    return StockResponse(
        product_code=product.product_code,
        stock=product.stock,
        product=product,
    )


@router.get("/price", response_model=PriceResponse)
def get_product_price(
    product_code_or_name: str = Query(...),
    service: ProductService = Depends(get_product_service),
) -> PriceResponse:
    product = service.get_product_details(product_code_or_name)

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    return PriceResponse(
        product_code=product.product_code,
        price=product.price,
        currency=service.target_currency,
        product=product,
    )


@router.get("/stock/total")
def get_total_stock(
    query: str | None = Query(default=None),
    product_code: str | None = Query(default=None),
    name: str | None = Query(default=None),
    brand: str | None = Query(default=None),
    min_stock: int | None = Query(default=None, ge=0),
    max_stock: int | None = Query(default=None, ge=0),
    service: ProductService = Depends(get_product_service),
) -> dict[str, int]:
    filters = ProductSearchFilters(
        query=query,
        product_code=product_code,
        name=name,
        brand=brand,
        min_stock=min_stock,
        max_stock=max_stock,
    )

    return {"total_stock": service.get_total_stock(filters)}
