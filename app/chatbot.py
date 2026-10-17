from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from app.config import get_settings
from app.conversation_store import ConversationStore
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
        self.conversation_store = conversation_store or ConversationStore()
        self.client = client or OpenAI(api_key=settings.openai_api_key.get_secret_value())
        self.model = model or settings.openai_model
        self.max_rounds = max_rounds
        self.history_limit = history_limit or settings.chat_history_limit

    def chat(
        self,
        message: str,
        conversation_id: str | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> ChatbotResult:
        active_conversation_id = self._get_or_create_conversation_id(conversation_id)
        stored_history = self.conversation_store.get_messages(
            active_conversation_id,
            limit=self.history_limit,
        )

        messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self._records_to_openai_messages(stored_history))
        messages.extend(self._sanitize_history(history))
        messages.append({"role": "user", "content": message})

        tool_calls_seen: list[str] = []

        logger.info(
            "chat.start conversation_id=%s model=%s history_items=%s message=%r",
            active_conversation_id,
            self.model,
            len(stored_history),
            message,
        )

        self.conversation_store.add_message(active_conversation_id, "user", message)

        for round_number in range(1, self.max_rounds + 1):
            logger.debug(
                "chat.round.start conversation_id=%s round=%s messages=%s",
                active_conversation_id,
                round_number,
                len(messages),
            )
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=PRODUCT_TOOLS,
                tool_choice="auto",
            )

            assistant_message = response.choices[0].message
            tool_calls = assistant_message.tool_calls or []

            logger.debug(
                "chat.openai_response conversation_id=%s round=%s response_id=%s finish_reason=%s content=%r tool_calls=%s",
                active_conversation_id,
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
            self.conversation_store.add_message(
                active_conversation_id,
                "assistant",
                assistant_message.content or "",
                tool_calls=assistant_payload.get("tool_calls"),
            )

            if not tool_calls:
                logger.info(
                    "chat.final_response conversation_id=%s round=%s tool_calls=%s answer=%r",
                    active_conversation_id,
                    round_number,
                    tool_calls_seen,
                    assistant_message.content,
                )
                return ChatbotResult(
                    conversation_id=active_conversation_id,
                    answer=assistant_message.content or "",
                    tool_calls=tool_calls_seen,
                )

            for tool_call in tool_calls:
                arguments = self._parse_arguments(tool_call.function.arguments)
                tool_calls_seen.append(tool_call.function.name)
                logger.info(
                    "chat.tool_call conversation_id=%s round=%s function=%s arguments=%s",
                    active_conversation_id,
                    round_number,
                    tool_call.function.name,
                    arguments,
                )
                result = execute_product_tool(
                    self.product_service,
                    tool_call.function.name,
                    arguments,
                )
                tool_result_text = dumps_tool_result(result)
                logger.debug(
                    "chat.tool_result conversation_id=%s round=%s function=%s result=%s",
                    active_conversation_id,
                    round_number,
                    tool_call.function.name,
                    self._truncate(tool_result_text),
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result_text,
                    }
                )
                self.conversation_store.add_message(
                    active_conversation_id,
                    "tool",
                    tool_result_text,
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.function.name,
                )

        raise RuntimeError("Chatbot exceeded maximum tool-calling rounds")

    def _get_or_create_conversation_id(self, conversation_id: str | None) -> str:
        if conversation_id is None:
            conversation = self.conversation_store.create_conversation()
            return conversation.conversation_id

        conversation_id = conversation_id.strip()
        if not conversation_id:
            raise ValueError("conversation_id cannot be empty")

        conversation = self.conversation_store.get_conversation(conversation_id)
        return conversation.conversation_id

    @staticmethod
    def _sanitize_history(history: list[dict[str, str]] | None) -> list[dict[str, str]]:
        if not history:
            return []

        messages: list[dict[str, str]] = []
        for item in history:
            role = item.get("role")
            content = item.get("content")
            if role in {"user", "assistant", "system"} and content is not None:
                messages.append({"role": role, "content": content})
        return messages

    @staticmethod
    def _records_to_openai_messages(records: list[Any]) -> list[dict[str, Any]]:
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
            else:
                messages.append({"role": record.role, "content": record.content or ""})
        return messages

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
