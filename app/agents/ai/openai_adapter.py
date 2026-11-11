
import inspect
import json
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel

from app.agents.ai.dto import AIResponse, AIToolCall


T = TypeVar("T", bound=BaseModel)


class OpenAIAdapter:
    def __init__(
        self,
        client: OpenAI,
        model: str,
    ) -> None:
        self.client = client
        self.model = model

    def create_completion(
        self,
        *,
        messages: list[dict],
        tools: list[dict],
    ) -> AIResponse:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
        )

        message = response.choices[0].message

        tool_calls = [
            AIToolCall(
                id=item.id,
                name=item.function.name,
                arguments=item.function.arguments,
            )
            for item in (message.tool_calls or [])
        ]

        return AIResponse(
            content=message.content,
            tool_calls=tool_calls,
        )

    def create_structured_completion(
        self,
        *,
        messages: list[dict],
        response_format: type[T],
    ) -> T:

        response = self.client.chat.completions.parse(
            model=self.model,
            messages=messages,
            response_format=response_format,
        )

        parsed = response.choices[0].message.parsed

        if parsed is None:
            raise ValueError("OpenAI returned an empty structured response.")

        return parsed
