
from __future__ import annotations

import logging
from typing import Any

from app.agents.ai.ai_client import AIClient
from app.agents.schemes.agent_execution_result import AgentExecutionResult
from app.agents.tools.tool_call_handler import ToolCallHandler
from app.agents.tools.tool_history_validator import ToolHistoryValidator
from app.agents.tools.product_tools import PRODUCT_TOOLS


logger = logging.getLogger(__name__)


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
            raise ValueError("max_iterations must be greater than or equal to 1")

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

        executed_tool_names: list[str] = []
        last_search_result: dict[str, Any] | None = None

        logger.info(
            "Agent execution started: conversation_id=%s max_iterations=%s",
            conversation_id,
            self.max_iterations,
        )

        for iteration in range(1, self.max_iterations + 1):
            logger.info(
                "Agent iteration started: conversation_id=%s iteration=%s",
                conversation_id,
                iteration,
            )

            self.tool_history_validator.validate(
                messages,
                conversation_id=conversation_id,
            )

            try:
                response = self.ai_client.create_completion(
                    messages=messages,
                    tools=PRODUCT_TOOLS,
                )
            except Exception:
                logger.exception(
                    "AI completion failed: conversation_id=%s iteration=%s",
                    conversation_id,
                    iteration,
                )
                raise

            if not response.tool_calls:
                answer = response.content or ""

                logger.info(
                    "Agent execution completed: conversation_id=%s "
                    "iterations=%s tool_count=%s answer_length=%s",
                    conversation_id,
                    iteration,
                    len(executed_tool_names),
                    len(answer),
                )

                return AgentExecutionResult(
                    answer=answer,
                    tool_calls=executed_tool_names,
                    last_search_result=last_search_result,
                )

            logger.info(
                "AI requested tools: conversation_id=%s iteration=%s "
                "tool_count=%s tool_names=%s",
                conversation_id,
                iteration,
                len(response.tool_calls),
                [tool_call.name for tool_call in response.tool_calls],
            )

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
                    "Tool call handling failed: conversation_id=%s iteration=%s",
                    conversation_id,
                    iteration,
                )
                raise

            executed_tool_names.extend(handling_result.tool_names)

            if handling_result.last_search_result is not None:
                last_search_result = handling_result.last_search_result

        logger.error(
            "Agent exceeded maximum iterations: conversation_id=%s "
            "max_iterations=%s tool_count=%s",
            conversation_id,
            self.max_iterations,
            len(executed_tool_names),
        )

        raise RuntimeError(
            f"Agent exceeded maximum tool-calling iterations "
            f"({self.max_iterations}) for conversation {conversation_id}"
        )
