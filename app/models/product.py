from typing import Any

from pydantic import BaseModel


class Product(BaseModel):
    product_id: str | None = None
    brand: str
    product_id_2: str | None = None
    model: str | None = None
    product_code: str | None = None
    name: str
    os: str | None = None
    price: float | None = None
    processor_name: str | None = None
    processor_brand: str | None = None
    ram_expandable: int = 0
    ram_gb: int | None = None
    ram_type: str | None = None
    processor_ghz: float | None = None
    display_type: str | None = None
    display_inch: float | None = None
    gpu: str | None = None
    gpu_brand: str | None = None
    ssd_gb: int | None = None
    hdd_gb: int | None = None
    stock: int = 0
    battery_life: str | None = None
    tags: str | None = None

    currency: str = "USD"

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Product":
        return cls.model_validate(row)