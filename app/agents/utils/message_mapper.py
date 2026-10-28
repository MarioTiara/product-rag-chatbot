
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class MessageMapper:
    @staticmethod
    def records_to_openai_messages(
        records: list[Any],
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []

        for record in records:
            if isinstance(record, dict):
                role = record.get("role")
                content = record.get("content") or ""
                tool_calls = record.get("tool_calls")
                tool_calls_json = record.get("tool_calls_json")
                tool_call_id = record.get("tool_call_id")
            else:
                role = getattr(record, "role", None)
                content = getattr(record, "content", None) or ""
                tool_calls = getattr(record, "tool_calls", None)
                tool_calls_json = getattr(
                    record, "tool_calls_json", None
                )
                tool_call_id = getattr(
                    record, "tool_call_id", None
                )

            if role == "assistant":
                message: dict[str, Any] = {
                    "role": "assistant",
                    "content": content,
                }

                if tool_calls is None and tool_calls_json:
                    try:
                        tool_calls = json.loads(tool_calls_json)
                    except (TypeError, json.JSONDecodeError):
                        logger.warning(
                            "Invalid tool_calls_json in history"
                        )
                        continue

                if tool_calls:
                    message["tool_calls"] = tool_calls

                messages.append(message)

            elif role == "tool":
                if not tool_call_id:
                    logger.warning(
                        "Skipping tool message without tool_call_id"
                    )
                    continue

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": content,
                })

            elif role == "user":
                messages.append({
                    "role": "user",
                    "content": content,
                })

        return messages

    @staticmethod
    def parse_tool_arguments(
        arguments: str,
    ) -> dict[str, Any]:
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
