from openai import OpenAI

from app.agents.ai.dto import AIResponse, AIToolCall


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