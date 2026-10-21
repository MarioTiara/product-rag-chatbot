
from __future__ import annotations

import json
from typing import Any

from app.schemes.product import ProductSearchFilters
from app.services.product_service import ProductService


PRODUCT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_product_details",
            "description": (
                "Get the details of a single product by its exact product name. "
                "Returns product specifications, price, currency, and stock "
                "when available. Use search_products if the product name is "
                "uncertain or multiple products may match."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The product name to look up.",
                    }
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": (
                "Search products by name, keywords, brand, specifications, "
                "price range, or stock range. Use this tool to find products "
                "matching customer requirements or to identify a product "
                "when its exact name is unknown. Prices use the configured "
                "target currency."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "General product search keywords.",
                    },
                    "product_code": {"type": "string"},
                    "name": {"type": "string"},
                    "brand": {"type": "string"},
                    "os": {"type": "string"},
                    "processor_brand": {"type": "string"},
                    "processor_name": {
                        "type": "string",
                        "description": "Processor family or model.",
                    },
                    "ram_expandable":{
                        "type": "string",
                        "description":"Expandle RAM capacity in GB",
                    },
                    "ram_gb": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "RAM capacity in GB.",
                    },
                    "min_ram": {
                        "type": "number",
                        "minimum": 0,
                        "description": "Minimum RAM capacity in GB.",
                    },
                    "max_ram": {
                        "type": "number",
                        "minimum": 0,
                        "description": "Maximum RAM capacity in GB.",
                    },
                    "ram_type": {"type": "string"},
                    "processor_ghz": {
                        "type": "number",
                        "minimum": 0,
                        "description": "Processor clock speed in GHz.",
                    },
                    "display_type": {"type": "string"},
                    "display_inch": {
                        "type": "number",
                        "minimum": 0,
                        "description": "Display size in inches.",
                    },
                    "gpu": {"type": "string"},
                    "gpu_brand": {"type": "string"},
                    "ssd_gb": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "SSD capacity in GB.",
                    },
                    "hdd_gb": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "HDD capacity in GB.",
                    },
                    "battery_life": {"type": "string"},
                    "min_price": {
                        "type": "number",
                        "minimum": 0,
                        "description": "Minimum price in target currency.",
                    },
                    "max_price": {
                        "type": "number",
                        "minimum": 0,
                        "description": "Maximum price in target currency.",
                    },
                    "min_stock": {
                        "type": "integer",
                        "minimum": 0,
                    },
                    "max_stock": {
                        "type": "integer",
                        "minimum": 0,
                    },
                    "sort_by": {
                        "type": "string",
                        "enum": ["price", "stock", "ram", "name"],
                        "description": "Field used to sort results.",
                    },
                    "sort_order": {
                        "type": "string",
                        "enum": ["asc", "desc"],
                        "description": "Sort direction.",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                    },
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_product_availability",
            "description": (
                "Check whether a specific product is available based on its "
                "current stock. Use the product's name. If the exact name is "
                "unknown, call search_products first. A missing product and "
                "a product with zero stock are different outcomes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The exact product name to check.",
                    }
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_total_stock",
            "description": (
                "Calculate the total number of stock units across all products "
                "matching the provided filters. Use this for aggregate stock "
                "questions, such as total stock by brand or category. "
                "Do not interpret the result as the number of matching products. "
                "Sorting and limit do not restrict the aggregate calculation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "product_code": {"type": "string"},
                    "name": {"type": "string"},
                    "brand": {"type": "string"},
                    "os": {"type": "string"},
                    "processor_brand": {"type": "string"},
                    "processor_name": {"type": "string"},
                    "ram_expandable": {"type": "string"},
                    "ram_gb": {"type": "integer", "minimum": 0},
                    "min_ram": {"type": "number", "minimum": 0},
                    "max_ram": {"type": "number", "minimum": 0},
                    "ram_type": {"type": "string"},
                    "processor_ghz": {"type": "number", "minimum": 0},
                    "display_type": {"type": "string"},
                    "display_inch": {"type": "number", "minimum": 0},
                    "gpu": {"type": "string"},
                    "gpu_brand": {"type": "string"},
                    "ssd_gb": {"type": "integer", "minimum": 0},
                    "hdd_gb": {"type": "integer", "minimum": 0},
                    "battery_life": {"type": "string"},
                    "min_price": {"type": "number", "minimum": 0},
                    "max_price": {"type": "number", "minimum": 0},
                    "min_stock": {"type": "integer", "minimum": 0},
                    "max_stock": {"type": "integer", "minimum": 0},
                    "sort_by": {
                        "type": "string",
                        "enum": ["price", "stock", "ram", "name"],
                    },
                    "sort_order": {
                        "type": "string",
                        "enum": ["asc", "desc"],
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                    },
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
        name = str(tool_arguments.get("name", "")).strip()

        if not name:
            return {"product": None, "error": "Product name is required."}

        product = service.get_product_details(name)

        return {
            "product": product.model_dump() if product else None,
        }

    if tool_name == "search_products":
        filters = ProductSearchFilters.model_validate(tool_arguments)
        products = service.search_products(filters)

        return {
            "count": len(products),
            "products": [
                product.model_dump()
                for product in products
            ],
        }

    if tool_name == "check_product_availability":
        name = str(tool_arguments.get("name", "")).strip()

        if not name:
            return {
                "product_name": "",
                "available": None,
                "stock": None,
                "error": "Product name is required.",
            }

        result = service.check_product_availability(name)

        if result is None:
            return {
                "product_name": name,
                "available": None,
                "stock": None,
                "error": "Product not found.",
            }

        return result

    if tool_name == "get_total_stock":
        filters = ProductSearchFilters.model_validate(tool_arguments)

        return {
            "total_stock": service.get_total_stock(filters),
            "filters": filters.model_dump(exclude_none=True),
        }

    raise ValueError(f"Unknown product tool: {tool_name}")


def dumps_tool_result(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)
