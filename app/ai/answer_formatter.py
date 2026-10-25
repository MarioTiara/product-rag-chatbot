
from __future__ import annotations

from typing import Any


class AnswerFormatter:
    @staticmethod
    def format_price(
        price: float | None,
        currency: str = "IDR",
    ) -> str:
        if price is None:
            return f"{currency} -"

        rounded = int(round(price))
        return f"{currency} {rounded:,}".replace(",", ".")

    @staticmethod
    def looks_like_no_match_answer(answer: str) -> bool:
        text = answer.lower()

        return any(
            phrase in text
            for phrase in (
                "no matching",
                "no products",
                "no result",
                "tidak ada",
                "tidak menemukan",
                "tidak tersedia",
                "tidak cocok",
            )
        )

    def finalize_search_answer(
        self,
        answer: str,
        result: dict[str, Any],
    ) -> str:
        count = int(result.get("count") or 0)
        products = result.get("products") or []

        if count <= 0 or not products:
            return (
                "Sorry, I couldn't find any matching products "
                "in our database."
            )

        if not self.looks_like_no_match_answer(answer):
            return answer

        product = products[0]
        price = self.format_price(
            product.get("price"),
            product.get("currency", "IDR"),
        )

        return (
            f"I found {count} matching product(s). "
            f"One option is {product.get('name')}, "
            f"priced at {price}."
        )
