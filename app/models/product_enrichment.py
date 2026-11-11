from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NormalizedAttribute(BaseModel):
    name: str = Field(description="Attribute name.")
    value: str = Field(description="Normalized attribute value.")
    
class ProductEnrichment(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int | None = None
    product_code: str

    description: str
    use_cases: list[str]
    target_users: list[str]
    key_features: list[str]
    limitations: list[str]

    normalized_attributes: dict[str, Any]

    status: str = "pending"

    model_name: str | None = None
    prompt_version: str | None = None
    source_hash: str | None = None

    created_at: str | None = None
    updated_at: str | None = None


class ProductEnrichmentInput(BaseModel):
    product_code: str
    brand: str | None = None
    model: str | None = None
    processor: str | None = None
    ram_gb: int | None = None
    ssd_gb: int | None = None
    hdd_gb: int | None = None
    gpu: str | None = None
    display_inch: float | None = None
    os: str | None = None
    price: float | None = None
    battery_life: str | None = None


class ProductEnrichmentOutput(BaseModel):
    description: str = Field(min_length=20)
    use_cases: list[str]
    target_users: list[str]
    key_features: list[str]
    limitations: list[str]
    normalized_attributes: list[NormalizedAttribute]