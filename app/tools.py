from __future__ import annotations

import json
from typing import Any

from app.models import ProductSearchFilters
from app.product_service import ProductService


PRODUCT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_product_details",
            "description": "Get the full details for a single product by SKU or product name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku_or_name": {
                        "type": "string",
                        "description": "The product SKU or product name.",
                    }
                },
                "required": ["sku_or_name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search products using keywords, specifications, category, brand, price, or stock filters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "General search text."},
                    "sku": {"type": "string"},
                    "name": {"type": "string"},
                    "category": {"type": "string"},
                    "brand": {"type": "string"},
                    "processor_brand": {"type": "string"},
                    "processor_name": {"type": "string"},
                    "ram_expandable": {"type": "string"},
                    "ram": {"type": "string"},
                    "display_type": {"type": "string"},
                    "ram_type": {"type": "string"},
                    "ghz": {"type": "string"},
                    "display": {"type": "string"},
                    "gpu": {"type": "string"},
                    "gpu_brand": {"type": "string"},
                    "ssd": {"type": "string"},
                    "hdd": {"type": "string"},
                    "battery_life": {"type": "string"},
                    "min_price": {"type": "number", "minimum": 0},
                    "max_price": {"type": "number", "minimum": 0},
                    "min_stock": {"type": "integer", "minimum": 0},
                    "max_stock": {"type": "integer", "minimum": 0},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_stock",
            "description": "Get the current stock quantity for a product by SKU or name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku_or_name": {"type": "string"},
                },
                "required": ["sku_or_name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_price",
            "description": "Get the current price for a product by SKU or name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku_or_name": {"type": "string"},
                },
                "required": ["sku_or_name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_total_stock",
            "description": "Get the total stock quantity for products matching the same filters as search_products.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "General search text."},
                    "sku": {"type": "string"},
                    "name": {"type": "string"},
                    "category": {"type": "string"},
                    "brand": {"type": "string"},
                    "processor_brand": {"type": "string"},
                    "processor_name": {"type": "string"},
                    "ram_expandable": {"type": "string"},
                    "ram": {"type": "string"},
                    "display_type": {"type": "string"},
                    "ram_type": {"type": "string"},
                    "ghz": {"type": "string"},
                    "display": {"type": "string"},
                    "gpu": {"type": "string"},
                    "gpu_brand": {"type": "string"},
                    "ssd": {"type": "string"},
                    "hdd": {"type": "string"},
                    "battery_life": {"type": "string"},
                    "min_price": {"type": "number", "minimum": 0},
                    "max_price": {"type": "number", "minimum": 0},
                    "min_stock": {"type": "integer", "minimum": 0},
                    "max_stock": {"type": "integer", "minimum": 0},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                "additionalProperties": False,
            },
        },
    },
]


def execute_product_tool(
    service: ProductService,
    tool_name: str,
    tool_arguments: dict[str, Any],
) -> dict[str, Any]:
    if tool_name == "get_product_details":
        sku_or_name = str(tool_arguments.get("sku_or_name", "")).strip()
        product = service.get_product_details(sku_or_name)
        return {"product": product.model_dump() if product else None}

    if tool_name == "search_products":
        filters = ProductSearchFilters.model_validate(tool_arguments)
        products = service.search_products(filters)
        return {
            "count": len(products),
            "products": [product.model_dump() for product in products],
        }

    if tool_name == "get_product_stock":
        sku_or_name = str(tool_arguments.get("sku_or_name", "")).strip()
        product = service.get_product_details(sku_or_name)
        stock = service.get_product_stock(sku_or_name)
        return {
            "sku_or_name": sku_or_name,
            "stock": stock,
            "product": product.model_dump() if product else None,
        }

    if tool_name == "get_product_price":
        sku_or_name = str(tool_arguments.get("sku_or_name", "")).strip()
        product = service.get_product_details(sku_or_name)
        price = service.get_product_price(sku_or_name)
        return {
            "sku_or_name": sku_or_name,
            "price": price,
            "currency": service.target_currency,
            "product": product.model_dump() if product else None,
        }

    if tool_name == "get_total_stock":
        filters = ProductSearchFilters.model_validate(tool_arguments)
        return {
            "total_stock": service.get_total_stock(filters),
            "filters": filters.model_dump(exclude_none=True),
        }

    raise ValueError(f"Unknown product tool: {tool_name}")


def dumps_tool_result(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)
