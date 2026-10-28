
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AgentExecutionResult:
    answer: str
    tool_calls: list[str]
    last_search_result: dict[str, Any] | None
