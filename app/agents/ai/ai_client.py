from typing import Protocol

from app.agents.ai.dto import AIResponse


class AIClient(Protocol):
    def create_completion(
        self,
        *,
        messages: list[dict],
        tools: list[dict],
    ) -> AIResponse:
        ...