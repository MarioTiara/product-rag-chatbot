from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from app.config import get_settings
from app.product_service import ProductService
from app.tools import PRODUCT_TOOLS, dumps_tool_result, execute_product_tool


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are a helpful product assistant. Use the provided tools for any factual "
    "product data such as price, stock, specs, and product matching. Never invent "
    "inventory or pricing details. If the database does not contain an exact match, "
    "say so clearly and suggest the closest available result when appropriate."
)


@dataclass(slots=True)
class ChatbotResult:
    answer: str
    tool_calls: list[str]


class ChatbotOrchestrator:
    def __init__(
        self,
        product_service: ProductService | None = None,
        client: OpenAI | None = None,
        model: str | None = None,
        max_rounds: int = 5,
    ) -> None:
        settings = get_settings()
        self.product_service = product_service or ProductService()
        self.client = client or OpenAI(api_key=settings.openai_api_key.get_secret_value())
        self.model = model or settings.openai_model
        self.max_rounds = max_rounds

    def chat(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
    ) -> ChatbotResult:
        messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]

        if history:
            for item in history:
                role = item.get("role")
                content = item.get("content")
                if role in {"user", "assistant", "system"} and content:
                    messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": message})

        tool_calls_seen: list[str] = []

        logger.info("chat.start model=%s history_items=%s message=%r", self.model, len(history or []), message)

        for round_number in range(1, self.max_rounds + 1):
            logger.debug("chat.round.start round=%s messages=%s", round_number, len(messages))
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=PRODUCT_TOOLS,
                tool_choice="auto",
            )

            assistant_message = response.choices[0].message
            tool_calls = assistant_message.tool_calls or []

            logger.debug(
                "chat.openai_response round=%s response_id=%s finish_reason=%s content=%r tool_calls=%s",
                round_number,
                getattr(response, "id", None),
                response.choices[0].finish_reason,
                assistant_message.content,
                [
                    {
                        "id": tool_call.id,
                        "name": tool_call.function.name,
                        "arguments": self._truncate(tool_call.function.arguments),
                    }
                    for tool_call in tool_calls
                ],
            )

            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_message.content or "",
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": tool_call.type,
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments,
                            },
                        }
                        for tool_call in tool_calls
                    ],
                }
            )

            if not tool_calls:
                logger.info(
                    "chat.final_response round=%s tool_calls=%s answer=%r",
                    round_number,
                    tool_calls_seen,
                    assistant_message.content,
                )
                return ChatbotResult(
                    answer=assistant_message.content or "",
                    tool_calls=tool_calls_seen,
                )

            for tool_call in tool_calls:
                arguments = self._parse_arguments(tool_call.function.arguments)
                tool_calls_seen.append(tool_call.function.name)
                logger.info(
                    "chat.tool_call round=%s function=%s arguments=%s",
                    round_number,
                    tool_call.function.name,
                    arguments,
                )
                result = execute_product_tool(
                    self.product_service,
                    tool_call.function.name,
                    arguments,
                )
                logger.debug(
                    "chat.tool_result round=%s function=%s result=%s",
                    round_number,
                    tool_call.function.name,
                    self._truncate(dumps_tool_result(result)),
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": dumps_tool_result(result),
                    }
                )

        raise RuntimeError("Chatbot exceeded maximum tool-calling rounds")

    @staticmethod
    def _parse_arguments(arguments: str) -> dict[str, Any]:
        if not arguments:
            return {}
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid tool arguments: {arguments}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("Tool arguments must be a JSON object")
        return parsed

    @staticmethod
    def _truncate(value: Any, limit: int = 1000) -> str:
        text = str(value)
        if len(text) <= limit:
            return text
        return f"{text[:limit]}...<truncated>"
