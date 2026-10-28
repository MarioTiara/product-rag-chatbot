
from __future__ import annotations

import json
import logging
from time import perf_counter
from typing import Any
from dataclasses import dataclass
from typing import Any

from app.agents.ai.dto import AIToolCall
from app.agents.tools.product_tools import (
    dumps_tool_result,
    execute_product_tool,
)


from app.services.conversation_service import ConversationService
from app.services.product_service import ProductService


# Create a logger specific to this module.
# It records tool execution events and errors for debugging and monitoring.
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ToolCallHandlingResult:
    """Store the outcome of handling a batch of tool calls."""

    # Names of the tools processed in the current execution round.
    tool_names: list[str]

    # The most recent product search result, if available.
    last_search_result: dict[str, Any] | None



class ToolCallHandler:
    """
    Handle tool calls requested by the AI.

    Responsibilities:
    1. Add the assistant's tool-call message to the message history.
    2. Persist the assistant's tool-call message to the database.
    3. Parse the tool arguments provided by the AI.
    4. Execute the requested tool.
    5. Serialize the tool result into a JSON string.
    6. Add the tool result to the message history.
    7. Persist the tool result to the database.
    8. Return the executed tool names and the latest search result.

    This class does not decide when the AI should call a tool.
    The AI makes that decision, while AgentExecutor manages the
    overall interaction loop between the AI and the tools.
    """

    def __init__(
        self,
        product_service: ProductService,
        conversation_service: ConversationService,
    ) -> None:
        """
        Initialize the handler with its required dependencies.

        Args:
            product_service:
                Provides business operations related to products,
                such as searching for products or checking stock.

            conversation_service:
                Persists conversation messages and tool results
                to the database.
        """

        # Used to execute product-related business operations.
        self.product_service = product_service

        # Used to persist conversation history.
        self.conversation_service = conversation_service

    def handle(
        self,
        tool_calls: list[AIToolCall],
        *,
        response_content: str | None,
        messages: list[dict[str, Any]],
        conversation_id: str,
        round_number: int,
    ) -> ToolCallHandlingResult:
        """
        Execute all tool calls requested by the AI in the current round.

        Args:
            tool_calls:
                Tool calls requested by the AI, including each tool's
                ID, name, and arguments.

            response_content:
                Optional text content included in the assistant response.

            messages:
                The message history currently used by AgentExecutor.
                This list is updated so the resulting history can be
                sent back to the AI.

            conversation_id:
                ID of the conversation being processed.

            round_number:
                Current AI/tool execution round, used for logging.

        Returns:
            ToolCallHandlingResult containing:
            - tool_names: Names of the processed tools.
            - last_search_result: The most recent search result, if any.

        Execution flow:
            AI requests tools
                -> persist assistant tool-call message
                -> parse tool arguments
                -> execute each tool
                -> persist tool results
                -> return results to AgentExecutor
        """

        # If there are no tool calls, return an empty result.
        # This avoids requiring the caller to handle this case separately.
        if not tool_calls:
            return ToolCallHandlingResult(
                tool_names=[],
                last_search_result=None,
            )

        # Convert the internal DTOs into the tool_calls format expected
        # by the OpenAI Chat Completions API.
        #
        # This format allows the assistant's tool-call message to be
        # represented consistently in the conversation history.
        assistant_tool_calls = [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.name,
                    "arguments": tool_call.arguments,
                },
            }
            for tool_call in tool_calls
        ]

        # Add the assistant message before adding any tool responses.
        # Each tool response must refer to a tool_call_id that has
        # already been declared in the assistant's message.
        messages.append(
            {
                "role": "assistant",
                "content": response_content,
                "tool_calls": assistant_tool_calls,
            }
        )

        # Persist the assistant's tool-call message so the database
        # reflects the interaction between the assistant and the tools.
        #
        # If persistence fails, propagate the exception to the caller.
        self._persist_assistant_tool_calls(
            conversation_id=conversation_id,
            tool_calls=assistant_tool_calls,
        )

        # Collect the names of tools processed during this round.
        # The caller can use this information for logging or reporting.
        tool_names: list[str] = []

        # Store the latest product search result, if a tool returns one.
        # Other tools, such as stock checks, do not necessarily update it.
        last_search_result: dict[str, Any] | None = None

        # Execute each requested tool.
        # The AI may request multiple tools in a single response.
        for tool_call in tool_calls:
            # Start measuring the execution duration for logging.
            started_at = perf_counter()

            tool_name = tool_call.name

            logger.info(
                "Tool execution started: conversation_id=%s "
                "round=%s tool_call_id=%s tool_name=%s",
                conversation_id,
                round_number,
                tool_call.id,
                tool_name,
            )

            # Record the name of the tool being processed.
            tool_names.append(tool_name)

            try:
                # Tool arguments are usually provided as a JSON string.
                # Parse them into a Python dictionary before execution.
                arguments = self._parse_arguments(tool_call.arguments)

            except (TypeError, ValueError) as exc:
                # Invalid arguments should not terminate the entire round.
                # Instead, create an error result that the AI can interpret.
                #
                # The error is still returned as a role="tool" message,
                # ensuring this tool call receives a corresponding response.
                logger.warning(
                    "Invalid tool arguments: conversation_id=%s "
                    "tool_call_id=%s tool_name=%s error=%s",
                    conversation_id,
                    tool_call.id,
                    tool_name,
                    exc,
                )

                result: Any = {
                    "error": "Invalid tool arguments.",
                    "detail": str(exc),
                }

                # Serialize the error dictionary so it can be added
                # to the conversation history.
                result_text = self._serialize_result(result)

            else:
                # Arguments were parsed successfully.
                # Log them at DEBUG level to help with troubleshooting.
                logger.debug(
                    "Tool arguments parsed: conversation_id=%s "
                    "tool_name=%s arguments=%s",
                    conversation_id,
                    tool_name,
                    self._truncate(
                        self._serialize_result(arguments)
                    ),
                )

                try:
                    # Execute the requested tool.
                    #
                    # execute_product_tool selects the appropriate
                    # implementation based on the tool name and arguments.
                    result = execute_product_tool(
                        self.product_service,
                        tool_name,
                        arguments,
                    )

                    # Serialize the result into a JSON string so it
                    # can be returned to the AI.
                    result_text = dumps_tool_result(result)

                except Exception:
                    # Log the full traceback for internal debugging.
                    # Do not expose internal exception details directly
                    # to the AI.
                    logger.exception(
                        "Tool execution failed: conversation_id=%s "
                        "tool_call_id=%s tool_name=%s",
                        conversation_id,
                        tool_call.id,
                        tool_name,
                    )

                    # Return a controlled error message to the AI.
                    # The AI can use this information to formulate
                    # a response or decide what to do next.
                    result = {
                        "error": "Tool execution failed.",
                        "tool_name": tool_name,
                    }

                    result_text = self._serialize_result(result)

            # Add the tool result to the message history and persist it.
            #
            # The tool_call_id must match the ID from the assistant's
            # original tool-call request.
            self._append_and_persist_tool_result(
                messages=messages,
                conversation_id=conversation_id,
                tool_call_id=tool_call.id,
                tool_name=tool_name,
                content=result_text,
            )

            # Identify whether the result looks like a product search result.
            # If it is a dictionary containing a recognized result key,
            # store it as the latest search result.
            if self._is_search_result(result):
                last_search_result = result

            # Record the execution duration and result size.
            logger.info(
                "Tool execution completed: conversation_id=%s "
                "round=%s tool_call_id=%s tool_name=%s "
                "duration_ms=%.2f result_length=%s",
                conversation_id,
                round_number,
                tool_call.id,
                tool_name,
                (perf_counter() - started_at) * 1000,
                len(result_text),
            )

        # All tool calls in this round have been processed.
        # AgentExecutor can now send the updated message history back
        # to the AI to generate the final answer.
        return ToolCallHandlingResult(
            tool_names=tool_names,
            last_search_result=last_search_result,
        )

    def _persist_assistant_tool_calls(
        self,
        *,
        conversation_id: str,
        tool_calls: list[dict[str, Any]],
    ) -> None:
        """
        Persist the assistant's tool-call message to the database.

        Keeping this operation in a separate method makes the persistence
        responsibility easier to understand and maintain.
        """

        try:
            self.conversation_service.save_tool_call_message(
                conversation_id=conversation_id,
                tool_calls_json=self._serialize_result(tool_calls),
            )

        except Exception:
            # Do not silently ignore persistence failures.
            # The database history may otherwise become inconsistent
            # with the conversation state held by the application.
            logger.exception(
                "Failed to persist assistant tool calls: conversation_id=%s",
                conversation_id,
            )
            raise

    def _append_and_persist_tool_result(
        self,
        *,
        messages: list[dict[str, Any]],
        conversation_id: str,
        tool_call_id: str,
        tool_name: str,
        content: str,
    ) -> None:
        """
        Add a tool result to the message history and persist it.

        The role="tool" message tells the AI that the content is the
        result of a tool execution, rather than a user or assistant message.
        """

        # Add the result to the history that will be sent back to the AI.
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": content,
            }
        )

        try:
            # Persist the tool result to the database.
            # The tool_call_id associates this response with its request.
            self.conversation_service.save_tool_result(
                conversation_id=conversation_id,
                content=content,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
            )

        except Exception:
            # If persistence fails, propagate the exception.
            # Do not treat the operation as successful when the result
            # has not been saved correctly.
            logger.exception(
                "Failed to persist tool result: conversation_id=%s "
                "tool_call_id=%s tool_name=%s",
                conversation_id,
                tool_call_id,
                tool_name,
            )
            raise

    @staticmethod
    def _parse_arguments(
        arguments: str | dict[str, Any] | None,
    ) -> dict[str, Any]:
        """
        Convert tool arguments into a Python dictionary.

        Empty arguments are treated as an empty dictionary.
        String arguments must contain a valid JSON object.
        """

        # Some tools do not require any arguments.
        if arguments is None or arguments == "":
            return {}

        # If the arguments are already a dictionary, no JSON parsing
        # is necessary.
        if isinstance(arguments, dict):
            return arguments

        # Reject types other than strings and dictionaries.
        if not isinstance(arguments, str):
            raise TypeError(
                "Tool arguments must be a JSON string or dictionary."
            )

        try:
            # Convert the JSON string into a Python object.
            parsed = json.loads(arguments)

        except json.JSONDecodeError as exc:
            # Raise a clearer error than the raw JSON parser exception.
            raise ValueError(
                "Tool arguments contain invalid JSON."
            ) from exc

        # Tool arguments must be a JSON object, which becomes a Python
        # dictionary. JSON arrays, strings, numbers, and booleans are
        # not accepted.
        if not isinstance(parsed, dict):
            raise ValueError(
                "Tool arguments must decode to a JSON object."
            )

        return parsed

    @staticmethod
    def _serialize_result(value: Any) -> str:
        """
        Convert a Python value into a JSON string.

        ensure_ascii=False:
            Preserves Unicode characters instead of escaping them.

        separators:
            Produces compact JSON without unnecessary whitespace.

        default=str:
            Converts unsupported objects to strings as a fallback.
        """

        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )

    @staticmethod
    def _is_search_result(result: Any) -> bool:
        """
        Check whether a tool result appears to contain search results.

        The recognized keys accommodate common result formats
        used by search tools.
        """

        return isinstance(result, dict) and any(
            key in result for key in ("products", "items", "results")
        )

    @staticmethod
    def _truncate(value: str, limit: int = 2000) -> str:
        """
        Limit the length of text written to the logs.

        This prevents logs from becoming excessively large when
        tool arguments contain long values.
        """

        if len(value) <= limit:
            return value

        return f"{value[:limit]}... [truncated]"
