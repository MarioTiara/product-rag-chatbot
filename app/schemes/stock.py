from pydantic import BaseModel

from app.models.product import Product


class StockResponse(BaseModel):
    product_code: str
    stock: int
    product: Product


class PriceResponse(BaseModel):
    product_code: str
    price: float | None
    currency: str
    product: Product