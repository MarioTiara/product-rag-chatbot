
from __future__ import annotations

import logging
from typing import Any


logger = logging.getLogger(__name__)


class InvalidToolCallHistoryError(ValueError):
    """Raised when tool calls and their corresponding responses are inconsistent."""


class ToolHistoryValidator:
    """
    Validate the consistency of tool calls and tool responses in AI message history.

    When an AI requests a tool, the conversation history contains an assistant
    message with a `tool_calls` list. After the application executes each tool,
    it appends a corresponding message with `role="tool"`.

    This validator ensures that:
    1. Every tool call has a valid, unique ID.
    2. Every tool response references an existing tool call.
    3. Each tool call receives exactly one response.
    4. No tool calls remain unanswered.

    The validator should run before sending the message history back to the AI,
    preventing malformed tool-call sequences from being submitted to the provider.
    """

    def validate(
        self,
        messages: list[dict[str, Any]],
        *,
        conversation_id: str,
    ) -> None:
        """
        Validate all tool calls and tool responses in chronological order.

        Args:
            messages: Conversation history formatted as AI messages.
            conversation_id: ID used to identify the conversation in logs
                and error messages.

        Raises:
            InvalidToolCallHistoryError: If a tool call or its response is
                missing, duplicated, malformed, or references an unknown ID.

        Logic:
            - `seen_tool_call_ids` tracks every tool call ID encountered.
            - `pending_tool_calls` tracks tool calls that have not received
              a response yet.
            - When a valid tool response is encountered, its ID is removed
              from `pending_tool_calls`.
            - At the end, the pending set must be empty.
        """

        # Tracks all tool call IDs encountered in the history.
        # This prevents the same tool call ID from being declared twice.
        seen_tool_call_ids: set[str] = set()

        # Tracks tool calls that still need a corresponding tool response.
        # A tool call is added here when declared by the assistant and removed
        # when its matching role="tool" message is encountered.
        pending_tool_calls: set[str] = set()

        # Process messages in chronological order so responses are validated
        # against tool calls that have already appeared in the history.
        for message_index, message in enumerate(messages):
            role = message.get("role")

            # -------------------------------------------------------------
            # Case 1: Assistant message
            # -------------------------------------------------------------
            # An assistant message may contain tool calls requested by the AI.
            # For example:
            #
            # {
            #     "role": "assistant",
            #     "tool_calls": [
            #         {
            #             "id": "call_123",
            #             "type": "function",
            #             "function": {...}
            #         }
            #     ]
            # }
            #
            # Each declared tool call must have a unique, non-empty ID.
            if role == "assistant":
                tool_calls = message.get("tool_calls") or []

                # The tool_calls field must be a list when present.
                # An absent field or None means this assistant message
                # does not request any tools.
                if not isinstance(tool_calls, list):
                    self._raise_invalid_history(
                        conversation_id,
                        f"Invalid tool_calls at message index {message_index}.",
                    )

                for tool_call in tool_calls:
                    # Each tool call must be represented as a dictionary
                    # in the normalized message history.
                    if not isinstance(tool_call, dict):
                        self._raise_invalid_history(
                            conversation_id,
                            f"Malformed tool call at message index {message_index}.",
                        )

                    tool_call_id = tool_call.get("id")

                    # A tool call ID is required to associate the tool's
                    # eventual result with the correct request.
                    if not isinstance(tool_call_id, str) or not tool_call_id:
                        self._raise_invalid_history(
                            conversation_id,
                            f"Missing tool call ID at message index {message_index}.",
                        )

                    # Reject duplicate IDs. Otherwise, a tool response could
                    # not be associated unambiguously with one request.
                    if tool_call_id in seen_tool_call_ids:
                        self._raise_invalid_history(
                            conversation_id,
                            f"Duplicate tool call ID: {tool_call_id}.",
                        )

                    # Remember this ID permanently for duplicate detection.
                    seen_tool_call_ids.add(tool_call_id)

                    # The tool has been requested but has not been answered.
                    # It remains pending until its role="tool" message appears.
                    pending_tool_calls.add(tool_call_id)

            # -------------------------------------------------------------
            # Case 2: Tool response message
            # -------------------------------------------------------------
            # After the application executes a tool, it adds a message like:
            #
            # {
            #     "role": "tool",
            #     "tool_call_id": "call_123",
            #     "content": "{\"total_stock\": 25}"
            # }
            #
            # The response must reference a previously declared tool call.
            elif role == "tool":
                tool_call_id = message.get("tool_call_id")

                # Every tool response must identify the tool call it answers.
                if not isinstance(tool_call_id, str) or not tool_call_id:
                    self._raise_invalid_history(
                        conversation_id,
                        f"Missing tool_call_id at message index {message_index}.",
                    )

                # Reject responses that refer to a tool call that has never
                # appeared earlier in the message history.
                if tool_call_id not in seen_tool_call_ids:
                    self._raise_invalid_history(
                        conversation_id,
                        f"Unexpected tool response ID: {tool_call_id}.",
                    )

                # If the ID is known but no longer pending, a response has
                # already been received for that tool call.
                # This catches duplicate responses.
                if tool_call_id not in pending_tool_calls:
                    self._raise_invalid_history(
                        conversation_id,
                        f"Duplicate tool response ID: {tool_call_id}.",
                    )

                # The tool call has now received its response.
                # Removing the ID marks that request as completed.
                pending_tool_calls.remove(tool_call_id)

        # -------------------------------------------------------------
        # Final check: all tool calls must have received a response.
        # -------------------------------------------------------------
        # For example, if the assistant requested call_123 but the history
        # contains no matching role="tool" message, call_123 remains pending.
        #
        # Rejecting this history prevents an incomplete tool-call sequence
        # from being sent back to the AI.
        if pending_tool_calls:
            self._raise_invalid_history(
                conversation_id,
                f"Missing tool responses for IDs: {sorted(pending_tool_calls)}.",
            )

        # Reaching this point means all tool calls and responses are consistent.
        logger.debug(
            "Tool history validated: conversation_id=%s message_count=%s",
            conversation_id,
            len(messages),
        )

    @staticmethod
    def _raise_invalid_history(
        conversation_id: str,
        reason: str,
    ) -> None:
        """
        Log the validation failure and raise a specific exception.

        Keeping error construction in one place avoids repeating the same
        logging and exception logic in every validation branch.
        """
        logger.error(
            "Invalid tool history: conversation_id=%s reason=%s",
            conversation_id,
            reason,
        )

        raise InvalidToolCallHistoryError(
            f"Invalid tool history for conversation "
            f"{conversation_id}: {reason}"
        )
