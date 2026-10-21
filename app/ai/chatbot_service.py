
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from app.configs.config import get_settings
from app.services.conversation_store import ConversationStore
from app.services.product_service import ProductService
from app.ai.tools.product_tools import (
    PRODUCT_TOOLS,
    dumps_tool_result,
    execute_product_tool,
)


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are a helpful frontline customer service assistant for a store. "
    "Respond naturally and professionally in the user's language. "
    "Use the provided tools for factual product information, including "
    "product details, prices, stock availability, and product searches. "
    "Never invent product data, prices, or stock quantities. "
    "Use get_product_details when the exact product name is known. "
    "Use search_products when finding products by keywords, specifications, "
    "brand, price range, or other filters. "
    "Use check_product_availability to check whether a specific product "
    "is in stock. A product not found is different from a product with "
    "zero stock. "
    "Use get_total_stock for aggregate stock quantity questions. "
    "For minimum RAM requirements, use min_ram. "
    "For Intel Core i7, use processor_brand='Intel' and "
    "processor_name='Intel Core i7'. "
    "For cheapest products, use sort_by='price' and sort_order='asc'. "
    "For most expensive products, use sort_by='price' and "
    "sort_order='desc'. "
    "Only claim that no products match when the tool results support "
    "that conclusion. "
    "Use previous conversation messages to understand follow-up questions, "
    "but always use tools to verify current product information. "
    "Do not claim that an order has been placed or a purchase completed "
    "unless a corresponding tool explicitly confirms that action."
)


@dataclass(slots=True)
class ChatbotResult:
    conversation_id: str
    answer: str
    tool_calls: list[str]


class ChatbotOrchestrator:
    def __init__(
        self,
        product_service: ProductService | None = None,
        conversation_store: ConversationStore | None = None,
        client: OpenAI | None = None,
        model: str | None = None,
        max_rounds: int = 5,
        history_limit: int | None = None,
    ) -> None:
        settings = get_settings()

        self.product_service = product_service or ProductService()
        self.conversation_store = (
            conversation_store or ConversationStore()
        )
        self.client = client or OpenAI(
            api_key=settings.openai_api_key.get_secret_value()
        )
        self.model = model or settings.openai_model
        self.max_rounds = max_rounds
        self.history_limit = (
            history_limit
            if history_limit is not None
            else settings.chat_history_limit
        )

    def chat(
        self,
        message: str,
        conversation_id: str | None = None,
    ) -> ChatbotResult:
        message = message.strip()

        if not message:
            raise ValueError("Message cannot be empty")

        active_conversation_id = self._get_or_create_conversation_id(
            conversation_id
        )

        stored_history = self.conversation_store.get_messages(
            active_conversation_id,
            limit=self.history_limit,
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *self._records_to_openai_messages(stored_history),
            {"role": "user", "content": message},
        ]

        logger.info(
            "chat.start conversation_id=%s model=%s history_items=%s",
            active_conversation_id,
            self.model,
            len(stored_history),
        )

        # Persist the incoming user message.
        self.conversation_store.add_message(
            conversation_id=active_conversation_id,
            role="user",
            content=message,
        )

        last_search_result: dict[str, Any] | None = None
        executed_tool_calls: list[str] = []

        for round_number in range(1, self.max_rounds + 1):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=PRODUCT_TOOLS,
                tool_choice="auto",
            )

            assistant_message = response.choices[0].message
            tool_calls = assistant_message.tool_calls or []

            logger.debug(
                "chat.openai_response conversation_id=%s round=%s "
                "finish_reason=%s tool_calls=%s",
                active_conversation_id,
                round_number,
                response.choices[0].finish_reason,
                [call.function.name for call in tool_calls],
            )

            assistant_payload: dict[str, Any] = {
                "role": "assistant",
                "content": assistant_message.content or "",
            }

            if tool_calls:
                assistant_payload["tool_calls"] = [
                    {
                        "id": tool_call.id,
                        "type": tool_call.type,
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                    for tool_call in tool_calls
                ]

            messages.append(assistant_payload)

            # The assistant has finished responding.
            if not tool_calls:
                final_answer = assistant_message.content or ""

                if last_search_result is not None:
                    final_answer = self._finalize_search_answer(
                        final_answer,
                        last_search_result,
                    )

                self.conversation_store.add_message(
                    conversation_id=active_conversation_id,
                    role="assistant",
                    content=final_answer,
                )

                logger.info(
                    "chat.final_response conversation_id=%s round=%s "
                    "tool_calls=%s",
                    active_conversation_id,
                    round_number,
                    executed_tool_calls,
                )

                return ChatbotResult(
                    conversation_id=active_conversation_id,
                    answer=final_answer,
                    tool_calls=executed_tool_calls,
                )

            # Persist the assistant message containing tool calls
            # before persisting the corresponding tool results.
            self.conversation_store.add_message(
                conversation_id=active_conversation_id,
                role="assistant",
                content=assistant_message.content or "",
                tool_calls=assistant_payload["tool_calls"],
            )

            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                arguments = self._parse_arguments(
                    tool_call.function.arguments
                )

                logger.info(
                    "chat.tool_call conversation_id=%s round=%s "
                    "function=%s arguments=%s",
                    active_conversation_id,
                    round_number,
                    tool_name,
                    arguments,
                )

                result = execute_product_tool(
                    self.product_service,
                    tool_name,
                    arguments,
                )

                executed_tool_calls.append(tool_name)

                if tool_name == "search_products":
                    last_search_result = result

                tool_result_text = dumps_tool_result(result)

                # Add the result to the current OpenAI request history.
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result_text,
                    }
                )

                # Persist the tool result in SQLite.
                self.conversation_store.add_message(
                    conversation_id=active_conversation_id,
                    role="tool",
                    content=tool_result_text,
                    tool_call_id=tool_call.id,
                    tool_name=tool_name,
                )

                logger.debug(
                    "chat.tool_result conversation_id=%s round=%s "
                    "function=%s result=%s",
                    active_conversation_id,
                    round_number,
                    tool_name,
                    self._truncate(tool_result_text),
                )

        logger.warning(
            "chat.max_rounds_exceeded conversation_id=%s max_rounds=%s",
            active_conversation_id,
            self.max_rounds,
        )

        raise RuntimeError(
            "Chatbot exceeded maximum tool-calling rounds"
        )

    def _get_or_create_conversation_id(
        self,
        conversation_id: str | None,
    ) -> str:
        if conversation_id is None:
            conversation = self.conversation_store.create_conversation()
            return conversation.conversation_id

        conversation_id = conversation_id.strip()

        if not conversation_id:
            raise ValueError("conversation_id cannot be empty")

        conversation = self.conversation_store.get_conversation(
            conversation_id
        )

        return conversation.conversation_id

    @staticmethod
    def _records_to_openai_messages(
        records: list[Any],
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []

        for record in records:
            if record.role == "assistant":
                message: dict[str, Any] = {
                    "role": "assistant",
                    "content": record.content or "",
                }

                if record.tool_calls:
                    message["tool_calls"] = record.tool_calls

                messages.append(message)

            elif record.role == "tool":
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": record.tool_call_id,
                        "content": record.content or "",
                    }
                )

            elif record.role == "user":
                messages.append(
                    {
                        "role": "user",
                        "content": record.content or "",
                    }
                )

        return messages

    @staticmethod
    def _parse_arguments(
        arguments: str,
    ) -> dict[str, Any]:
        if not arguments:
            return {}

        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid tool arguments: {arguments}"
            ) from exc

        if not isinstance(parsed, dict):
            raise ValueError(
                "Tool arguments must be a JSON object"
            )

        return parsed

    @staticmethod
    def _truncate(
        value: Any,
        limit: int = 1000,
    ) -> str:
        text = str(value)

        if len(text) <= limit:
            return text

        return f"{text[:limit]}...<truncated>"

    @staticmethod
    def _looks_like_no_match_answer(
        answer: str,
    ) -> bool:
        text = answer.lower()

        return any(
            phrase in text
            for phrase in [
                "no matching",
                "no products",
                "no result",
                "tidak ada",
                "tidak menemukan",
                "tidak tersedia",
                "tidak cocok",
            ]
        )

    @staticmethod
    def _format_price(
        price: float | None,
        currency: str,
    ) -> str:
        if price is None:
            return f"{currency} -"

        rounded = int(round(price))

        return f"{currency} {rounded:,}".replace(",", ".")

    def _finalize_search_answer(
        self,
        assistant_answer: str,
        result: dict[str, Any],
    ) -> str:
        count = int(result.get("count") or 0)
        products = result.get("products") or []

        if count <= 0 or not products:
            return (
                "Sorry, I couldn't find any matching products "
                "in our database."
            )

        if not self._looks_like_no_match_answer(assistant_answer):
            return assistant_answer

        top_product = products[0]
        price_text = self._format_price(
            top_product.get("price"),
            top_product.get("currency", "IDR"),
        )

        return (
            f"I found {count} matching product(s). "
            f"One option is {top_product.get('name')}, "
            f"priced at {price_text}."
        )
