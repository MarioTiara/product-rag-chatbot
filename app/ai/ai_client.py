
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from openai import OpenAI


@dataclass(slots=True)
class AIToolCall:
    id: str
    name: str
    arguments: str


@dataclass(slots=True)
class AIResponse:
    content: str
    tool_calls: list[AIToolCall]


class AIClient(Protocol):
    def create_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AIResponse:
        """Generate a response using an AI provider."""
        ...


class OpenAIAdapter:
    """Translate OpenAI responses into the application's AI interface."""

    def __init__(
        self,
        client: OpenAI,
        model: str,
    ) -> None:
        self._client = client
        self._model = model

    def create_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AIResponse:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )

        if not response.choices:
            raise RuntimeError("AI provider returned no choices")

        assistant_message = response.choices[0].message

        normalized_tool_calls = [
            AIToolCall(
                id=call.id,
                name=call.function.name,
                arguments=call.function.arguments,
            )
            for call in (assistant_message.tool_calls or [])
        ]

        return AIResponse(
            content=assistant_message.content or "",
            tool_calls=normalized_tool_calls,
        )
