
from __future__ import annotations

from dataclasses import asdict
import logging
from time import perf_counter
from typing import Any

from app.agents.ai.ai_client import AIClient
from app.agents.schemes.agent_execution_result import AgentExecutionResult
from app.agents.tools.tool_call_handler import ToolCallHandler
from app.agents.tools.tool_history_validator import ToolHistoryValidator
from app.agents.tools.product_tools import PRODUCT_TOOLS


logger = logging.getLogger(__name__)


def _get_tool_arguments(tool_call: Any) -> Any:
    """Extract tool arguments without depending on a specific DTO type."""

    for attribute in ("arguments", "args", "parameters"):
        value = getattr(tool_call, attribute, None)

        if value is not None:
            return value

    return {}


class AgentExecutor:
    """Execute the AI agent loop, including tool calls and final responses."""

    def __init__(
        self,
        ai_client: AIClient,
        tool_call_handler: ToolCallHandler,
        tool_history_validator: ToolHistoryValidator,
        max_iterations: int = 5,
    ) -> None:
        if max_iterations < 1:
            raise ValueError(
                "max_iterations must be greater than or equal to 1"
            )

        self.ai_client = ai_client
        self.tool_call_handler = tool_call_handler
        self.tool_history_validator = tool_history_validator
        self.max_iterations = max_iterations

    def invoke(
        self,
        messages: list[dict[str, Any]],
        *,
        conversation_id: str,
    ) -> AgentExecutionResult:
        """Run the agent until the AI returns a final answer."""

        execution_started = perf_counter()
        executed_tool_names: list[str] = []
        last_search_result: dict[str, Any] | None = None

        logger.info(
            "Agent execution started",
            extra={
                "event": "agent_execution_started",
                "conversation_id": conversation_id,
                "max_iterations": self.max_iterations,
            },
        )

        for iteration in range(1, self.max_iterations + 1):
            logger.debug(
                "Agent iteration started",
                extra={
                    "event": "agent_iteration_started",
                    "conversation_id": conversation_id,
                    "iteration": iteration,
                },
            )

            self.tool_history_validator.validate(
                messages,
                conversation_id=conversation_id,
            )

            # Request completion from the AI provider.
            ai_started = perf_counter()

            try:
                response = self.ai_client.create_completion(
                    messages=messages,
                    tools=PRODUCT_TOOLS,
                )
                logger.debug(
                    "Full AI completion response",
                    extra={
                        "event": "ai_completion_response",
                        "conversation_id": conversation_id,
                        "iteration": iteration,
                        "ai_response": asdict(response),
                    },
                )
                
            except Exception:
                logger.exception(
                    "AI completion failed",
                    extra={
                        "event": "ai_completion_failed",
                        "conversation_id": conversation_id,
                        "iteration": iteration,
                        "duration_ms": round(
                            (perf_counter() - ai_started) * 1000,
                            2,
                        ),
                    },
                )
                raise

            logger.info(
                "AI completion received",
                extra={
                    "event": "ai_completion_completed",
                    "conversation_id": conversation_id,
                    "iteration": iteration,
                    "tool_call_count": len(response.tool_calls),
                    "has_final_content": bool(response.content),
                    "duration_ms": round(
                        (perf_counter() - ai_started) * 1000,
                        2,
                    ),
                },
            )

            # The AI returned a final answer instead of tool calls.
            if not response.tool_calls:
                answer = response.content or ""

                logger.info(
                    "Agent execution completed",
                    extra={
                        "event": "agent_execution_completed",
                        "conversation_id": conversation_id,
                        "iterations": iteration,
                        "tool_count": len(executed_tool_names),
                        "tool_names": executed_tool_names,
                        "answer_length": len(answer),
                        "duration_ms": round(
                            (perf_counter() - execution_started) * 1000,
                            2,
                        ),
                    },
                )

                return AgentExecutionResult(
                    answer=answer,
                    tool_calls=executed_tool_names,
                    last_search_result=last_search_result,
                )

            # Record exactly which tools and arguments the AI requested.
            requested_tools = [
                {
                    "tool_name": tool_call.name,
                    "arguments": _get_tool_arguments(tool_call),
                }
                for tool_call in response.tool_calls
            ]

            logger.info(
                "AI requested tool calls",
                extra={
                    "event": "ai_tool_calls_requested",
                    "conversation_id": conversation_id,
                    "iteration": iteration,
                    "tool_call_count": len(requested_tools),
                    "requested_tools": requested_tools,
                },
            )

            # Execute the requested tools.
            tool_started = perf_counter()

            try:
                handling_result = self.tool_call_handler.handle(
                    response.tool_calls,
                    response_content=response.content,
                    messages=messages,
                    conversation_id=conversation_id,
                    round_number=iteration,
                )
            except Exception:
                logger.exception(
                    "Tool call handling failed",
                    extra={
                        "event": "tool_call_handling_failed",
                        "conversation_id": conversation_id,
                        "iteration": iteration,
                        "requested_tools": requested_tools,
                        "duration_ms": round(
                            (perf_counter() - tool_started) * 1000,
                            2,
                        ),
                    },
                )
                raise

            executed_tool_names.extend(handling_result.tool_names)

            if handling_result.last_search_result is not None:
                last_search_result = handling_result.last_search_result

            logger.info(
                "Tool call handling completed",
                extra={
                    "event": "tool_call_handling_completed",
                    "conversation_id": conversation_id,
                    "iteration": iteration,
                    "requested_tool_count": len(requested_tools),
                    "executed_tool_names": handling_result.tool_names,
                    "last_search_result_available": (
                        handling_result.last_search_result is not None
                    ),
                    "duration_ms": round(
                        (perf_counter() - tool_started) * 1000,
                        2,
                    ),
                },
            )

        logger.error(
            "Agent exceeded maximum iterations",
            extra={
                "event": "agent_max_iterations_exceeded",
                "conversation_id": conversation_id,
                "max_iterations": self.max_iterations,
                "tool_count": len(executed_tool_names),
                "tool_names": executed_tool_names,
                "duration_ms": round(
                    (perf_counter() - execution_started) * 1000,
                    2,
                ),
            },
        )

        raise RuntimeError(
            "Agent exceeded maximum tool-calling iterations "
            f"({self.max_iterations}) for conversation {conversation_id}"
        )
