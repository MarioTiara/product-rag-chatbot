from typing import Protocol

from pydantic import BaseModel

from app.agents.ai.dto import AIResponse


class AIClient(Protocol):
    def create_completion(
        self,
        *,
        messages: list[dict],
        tools: list[dict],
    ) -> AIResponse:
        ...
        
    def create_structured_completion(
            self,
            *,
            messages: list[dict],
            response_format: type[BaseModel],
        ) -> BaseModel:
            ...