
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from app.ai.ai_client import AIClient
from app.ai.tools.product_tools import (
    PRODUCT_TOOLS,
    dumps_tool_result,
    execute_product_tool,
)
from app.services.conversation_service import ConversationService
from app.services.product_service import ProductService


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ProductChatAgentResult:
    answer: str
    tool_calls: list[str]
    last_search_result: dict[str, Any] | None = None


class ProductChatAgent:
    """Run the AI tool-calling loop for product-related conversations."""

    def __init__(
        self,
        ai_client: AIClient,
        product_service: ProductService,
        conversation_service: ConversationService,
        max_rounds: int = 5,
    ) -> None:
        if max_rounds < 1:
            raise ValueError("max_rounds must be at least 1")

        self.ai_client = ai_client
        self.product_service = product_service
        self.conversation_service = conversation_service
        self.max_rounds = max_rounds

    def generate(
        self,
        messages: list[dict[str, Any]],
        *,
        conversation_id: str,
    ) -> ProductChatAgentResult:
        executed_tool_calls: list[str] = []
        last_search_result: dict[str, Any] | None = None

        for round_number in range(1, self.max_rounds + 1):
            response = self.ai_client.create_completion(
                messages=messages,
                tools=PRODUCT_TOOLS,
            )

            assistant_payload: dict[str, Any] = {
                "role": "assistant",
                "content": response.content,
            }

            if response.tool_calls:
                assistant_payload["tool_calls"] = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": call.arguments,
                        },
                    }
                    for call in response.tool_calls
                ]

            messages.append(assistant_payload)

            logger.debug(
                "agent.response conversation_id=%s round=%s "
                "tool_calls=%s",
                conversation_id,
                round_number,
                [call.name for call in response.tool_calls],
            )

            if not response.tool_calls:
                return ProductChatAgentResult(
                    answer=response.content,
                    tool_calls=executed_tool_calls,
                    last_search_result=last_search_result,
                )

            self.conversation_service.save_tool_call_message(
                conversation_id=conversation_id,
                tool_calls_json=json.dumps(
                    assistant_payload["tool_calls"],
                    ensure_ascii=False,
                ),
            )

            for tool_call in response.tool_calls:
                arguments = self._parse_arguments(
                    tool_call.arguments
                )

                logger.info(
                    "agent.tool_call conversation_id=%s round=%s "
                    "function=%s arguments=%s",
                    conversation_id,
                    round_number,
                    tool_call.name,
                    arguments,
                )

                result = execute_product_tool(
                    self.product_service,
                    tool_call.name,
                    arguments,
                )

                executed_tool_calls.append(tool_call.name)

                if tool_call.name == "search_products":
                    last_search_result = result

                tool_result_text = dumps_tool_result(result)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result_text,
                    }
                )

                self.conversation_service.save_tool_result(
                    conversation_id=conversation_id,
                    content=tool_result_text,
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.name,
                )

                logger.debug(
                    "agent.tool_result conversation_id=%s "
                    "function=%s result=%s",
                    conversation_id,
                    tool_call.name,
                    self._truncate(tool_result_text),
                )

        logger.warning(
            "agent.max_rounds_exceeded conversation_id=%s max_rounds=%s",
            conversation_id,
            self.max_rounds,
        )

        raise RuntimeError(
            "Agent exceeded maximum tool-calling rounds"
        )

    @staticmethod
    def _parse_arguments(arguments: str) -> dict[str, Any]:
        if not arguments:
            return {}

        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Invalid JSON in tool arguments"
            ) from exc

        if not isinstance(parsed, dict):
            raise ValueError(
                "Tool arguments must be a JSON object"
            )

        return parsed

    @staticmethod
    def _truncate(value: Any, limit: int = 1000) -> str:
        text = str(value)

        if len(text) <= limit:
            return text

        return f"{text[:limit]}...<truncated>"
