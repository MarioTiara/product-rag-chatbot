
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from app.agents.ai.dto import AIToolCall
from app.agents.tools.product_tools import (
    dumps_tool_result,
    execute_product_tool,
)
from app.services.conversation_service import ConversationService
from app.services.product_service import ProductService


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ToolCallHandlingResult:
    """Store the outcome of handling a batch of tool calls."""

    tool_names: list[str]
    last_search_result: dict[str, Any] | None


class ToolCallHandler:
    """Execute AI-requested tools and persist their results."""

    def __init__(
        self,
        product_service: ProductService,
        conversation_service: ConversationService,
    ) -> None:
        self.product_service = product_service
        self.conversation_service = conversation_service

    def handle(
        self,
        tool_calls: list[AIToolCall],
        *,
        response_content: str | None,
        messages: list[dict[str, Any]],
        conversation_id: str,
        round_number: int,
    ) -> ToolCallHandlingResult:
        """Execute all tool calls requested by the AI in this round."""

        if not tool_calls:
            return ToolCallHandlingResult(
                tool_names=[],
                last_search_result=None,
            )

        round_started = perf_counter()

        assistant_tool_calls = [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.name,
                    "arguments": tool_call.arguments,
                },
            }
            for tool_call in tool_calls
        ]

        messages.append(
            {
                "role": "assistant",
                "content": response_content,
                "tool_calls": assistant_tool_calls,
            }
        )

        self._persist_assistant_tool_calls(
            conversation_id=conversation_id,
            tool_calls=assistant_tool_calls,
        )

        tool_names: list[str] = []
        last_search_result: dict[str, Any] | None = None

        logger.info(
            "Tool execution round started",
            extra={
                "event": "tool_execution_round_started",
                "conversation_id": conversation_id,
                "round_number": round_number,
                "tool_call_count": len(tool_calls),
                "requested_tool_names": [
                    tool_call.name for tool_call in tool_calls
                ],
            },
        )

        for tool_call in tool_calls:
            started_at = perf_counter()
            tool_name = tool_call.name
            arguments: dict[str, Any] | None = None

            tool_names.append(tool_name)

            logger.debug(
                "Tool execution started",
                extra={
                    "event": "tool_execution_started",
                    "conversation_id": conversation_id,
                    "round_number": round_number,
                    "tool_call_id": tool_call.id,
                    "tool_name": tool_name,
                },
            )

            # Parse arguments provided by the AI.
            try:
                arguments = self._parse_arguments(
                    tool_call.arguments
                )
            except (TypeError, ValueError) as exc:
                logger.warning(
                    "Invalid tool arguments",
                    extra={
                        "event": "tool_arguments_invalid",
                        "conversation_id": conversation_id,
                        "round_number": round_number,
                        "tool_call_id": tool_call.id,
                        "tool_name": tool_name,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "raw_arguments": self._truncate(
                            str(tool_call.arguments)
                        ),
                    },
                )

                result: Any = {
                    "error": "Invalid tool arguments.",
                    "detail": str(exc),
                }
                result_text = self._serialize_result(result)

            else:
                # Record the exact arguments passed to the tool.
                logger.debug(
                    "Tool arguments received",
                    extra={
                        "event": "tool_arguments_received",
                        "conversation_id": conversation_id,
                        "round_number": round_number,
                        "tool_call_id": tool_call.id,
                        "tool_name": tool_name,
                        "tool_arguments": arguments,
                    },
                )

                # Execute the requested tool.
                try:
                    result = execute_product_tool(
                        self.product_service,
                        tool_name,
                        arguments,
                    )
                    result_text = dumps_tool_result(result)

                except Exception as exc:
                    logger.exception(
                        "Tool execution failed",
                        extra={
                            "event": "tool_execution_failed",
                            "conversation_id": conversation_id,
                            "round_number": round_number,
                            "tool_call_id": tool_call.id,
                            "tool_name": tool_name,
                            "tool_arguments": arguments,
                            "error_type": type(exc).__name__,
                            "duration_ms": round(
                                (perf_counter() - started_at) * 1000,
                                2,
                            ),
                        },
                    )

                    result = {
                        "error": "Tool execution failed.",
                        "tool_name": tool_name,
                    }
                    result_text = self._serialize_result(result)

            has_error = (
                isinstance(result, dict) and "error" in result
            )

            # Record the complete tool result for debugging.
            logger.debug(
                "Tool execution result received",
                extra={
                    "event": "tool_execution_result_received",
                    "conversation_id": conversation_id,
                    "round_number": round_number,
                    "tool_call_id": tool_call.id,
                    "tool_name": tool_name,
                    "tool_arguments": arguments,
                    "tool_result": result,
                    "success": not has_error,
                    "duration_ms": round(
                        (perf_counter() - started_at) * 1000,
                        2,
                    ),
                },
            )

            # Append the result to AI history and persist it.
            try:
                self._append_and_persist_tool_result(
                    messages=messages,
                    conversation_id=conversation_id,
                    tool_call_id=tool_call.id,
                    tool_name=tool_name,
                    content=result_text,
                )
            except Exception as exc:
                logger.exception(
                    "Failed to persist tool result",
                    extra={
                        "event": "tool_result_persistence_failed",
                        "conversation_id": conversation_id,
                        "round_number": round_number,
                        "tool_call_id": tool_call.id,
                        "tool_name": tool_name,
                        "error_type": type(exc).__name__,
                        "duration_ms": round(
                            (perf_counter() - started_at) * 1000,
                            2,
                        ),
                    },
                )
                raise

            is_search_result = self._is_search_result(result)

            if is_search_result:
                last_search_result = result

            logger.info(
                "Tool execution completed",
                extra={
                    "event": "tool_execution_completed",
                    "conversation_id": conversation_id,
                    "round_number": round_number,
                    "tool_call_id": tool_call.id,
                    "tool_name": tool_name,
                    "success": not has_error,
                    "is_search_result": is_search_result,
                    "result_length": len(result_text),
                    "duration_ms": round(
                        (perf_counter() - started_at) * 1000,
                        2,
                    ),
                },
            )

        logger.info(
            "Tool execution round completed",
            extra={
                "event": "tool_execution_round_completed",
                "conversation_id": conversation_id,
                "round_number": round_number,
                "executed_tool_count": len(tool_names),
                "executed_tool_names": tool_names,
                "duration_ms": round(
                    (perf_counter() - round_started) * 1000,
                    2,
                ),
            },
        )

        return ToolCallHandlingResult(
            tool_names=tool_names,
            last_search_result=last_search_result,
        )

    def _persist_assistant_tool_calls(
        self,
        *,
        conversation_id: str,
        tool_calls: list[dict[str, Any]],
    ) -> None:
        """Persist the assistant's tool-call message."""

        try:
            self.conversation_service.save_tool_call_message(
                conversation_id=conversation_id,
                tool_calls_json=self._serialize_result(tool_calls),
            )
        except Exception as exc:
            logger.exception(
                "Failed to persist assistant tool calls",
                extra={
                    "event": "assistant_tool_calls_persistence_failed",
                    "conversation_id": conversation_id,
                    "tool_call_count": len(tool_calls),
                    "error_type": type(exc).__name__,
                },
            )
            raise

        logger.debug(
            "Assistant tool calls persisted",
            extra={
                "event": "assistant_tool_calls_persisted",
                "conversation_id": conversation_id,
                "tool_call_count": len(tool_calls),
            },
        )

    def _append_and_persist_tool_result(
        self,
        *,
        messages: list[dict[str, Any]],
        conversation_id: str,
        tool_call_id: str,
        tool_name: str,
        content: str,
    ) -> None:
        """Append a tool result to history and persist it."""

        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": content,
            }
        )

        self.conversation_service.save_tool_result(
            conversation_id=conversation_id,
            content=content,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
        )

        logger.debug(
            "Tool result persisted",
            extra={
                "event": "tool_result_persisted",
                "conversation_id": conversation_id,
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "result_length": len(content),
            },
        )

    @staticmethod
    def _parse_arguments(
        arguments: str | dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Parse tool arguments into a dictionary."""

        if arguments is None or arguments == "":
            return {}

        if isinstance(arguments, dict):
            return arguments

        if not isinstance(arguments, str):
            raise TypeError(
                "Tool arguments must be a JSON string or dictionary."
            )

        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Tool arguments contain invalid JSON."
            ) from exc

        if not isinstance(parsed, dict):
            raise ValueError(
                "Tool arguments must decode to a JSON object."
            )

        return parsed

    @staticmethod
    def _serialize_result(value: Any) -> str:
        """Serialize a value into compact JSON."""

        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )

    @staticmethod
    def _is_search_result(result: Any) -> bool:
        """Determine whether the result contains search results."""

        return isinstance(result, dict) and any(
            key in result for key in ("products", "items", "results")
        )

    @staticmethod
    def _truncate(value: str, limit: int = 2000) -> str:
        """Limit the size of values written to the logs."""

        if len(value) <= limit:
            return value

        return f"{value[:limit]}... [truncated]"
