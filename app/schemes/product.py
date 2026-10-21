
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ProductSearchFilters(BaseModel):
    # General search
    query: str | None = None

    # Product identification
    product_code: str | None = None
    name: str | None = None
    model: str | None = None
    brand: str | None = None
    os: str | None = None

    # Processor
    processor_name: str | None = None
    processor_brand: str | None = None
    min_ghz: float | None = Field(default=None, ge=0)
    max_ghz: float | None = Field(default=None, ge=0)

    # RAM
    ram_expandable: int | None = Field(default=None, ge=0)
    ram_type: str | None = None
    min_ram: int | None = Field(default=None, ge=0)
    max_ram: int | None = Field(default=None, ge=0)

    # Display
    display_type: str | None = None
    min_display: float | None = Field(default=None, gt=0)
    max_display: float | None = Field(default=None, gt=0)

    # Graphics
    gpu: str | None = None
    gpu_brand: str | None = None

    # Storage
    min_ssd: int | None = Field(default=None, ge=0)
    max_ssd: int | None = Field(default=None, ge=0)
    min_hdd: int | None = Field(default=None, ge=0)
    max_hdd: int | None = Field(default=None, ge=0)

    # Price
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)

    # Inventory
    min_stock: int | None = Field(default=None, ge=0)
    max_stock: int | None = Field(default=None, ge=0)

    # Sorting and pagination
    sort_by: Literal[
                    "price",
                    "stock",
                    "ram",
                    "name",
                ] ="name"
    sort_order: Literal["asc", "desc"] = "asc"
    limit: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def validate_ranges(self):
        ranges = [
            ("min_ram", "max_ram"),
            ("min_price", "max_price"),
            ("min_stock", "max_stock"),
            ("min_ghz", "max_ghz"),
            ("min_display", "max_display"),
            ("min_ssd", "max_ssd"),
            ("min_hdd", "max_hdd"),
        ]

        for minimum_field, maximum_field in ranges:
            minimum = getattr(self, minimum_field)
            maximum = getattr(self, maximum_field)

            if (
                minimum is not None
                and maximum is not None
                and minimum > maximum
            ):
                raise ValueError(
                    f"{minimum_field} cannot be greater than {maximum_field}"
                )

        return self
