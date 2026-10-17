from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Product(BaseModel):
    sku: str
    brand: str
    name: str
    category: str | None = None
    price: float | None = None
    processor_name: str | None = None
    processor_brand: str | None = None
    ram_expandable: str | None = None
    ram: str | None = None
    ram_type: str | None = None
    ghz: str | None = None
    display_type: str | None = None
    display: str | None = None
    gpu: str | None = None
    gpu_brand: str | None = None
    ssd: str | None = None
    hdd: str | None = None
    stock: int = 0
    battery_life: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Product":
        return cls.model_validate(row)


class ProductSearchFilters(BaseModel):
    query: str | None = None
    sku: str | None = None
    name: str | None = None
    category: str | None = None
    brand: str | None = None
    processor_brand: str | None = None
    processor_name: str | None = None
    ram: str | None = None
    ram_type: str | None = None
    display_type:str | None=None
    gpu_brand: str | None = None
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)
    min_stock: int | None = Field(default=None, ge=0)
    max_stock: int | None = Field(default=None, ge=0)
    limit: int = Field(default=20, ge=1, le=100)
