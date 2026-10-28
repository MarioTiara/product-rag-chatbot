from dataclasses import dataclass


@dataclass(slots=True)
class AIToolCall:
    id: str
    name: str
    arguments: str


@dataclass(slots=True)
class AIResponse:
    content: str
    tool_calls: list[AIToolCall]