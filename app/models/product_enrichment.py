
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
