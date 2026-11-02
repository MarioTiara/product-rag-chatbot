
from __future__ import annotations

import logging
from dataclasses import dataclass
from time import perf_counter

from app.agents.agent_executor import AgentExecutor
from app.agents.chat_context_builder import ChatContextBuilder
from app.agents.schemes.agent_execution_result import AgentExecutionResult
from app.services.conversation_service import ConversationService


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ChatbotResult:
    """Represent the final result returned by the chatbot."""

    conversation_id: str
    answer: str
    tool_calls: list[str]
    user_message_id: str
    assistant_message_id: str
    channel_conversation_id: int | None = None


class ChatbotOrchestrator:
    """Coordinate the chatbot request lifecycle."""

    def __init__(
        self,
        *,
        context_builder: ChatContextBuilder,
        agent_executor: AgentExecutor,
        conversation_service: ConversationService,
    ) -> None:
        self.context_builder = context_builder
        self.agent_executor = agent_executor
        self.conversation_service = conversation_service

    def chat(
        self,
        message: str,
        conversation_id: str | None = None,
        *,
        user_id: str | None = None,
        channel: str | None = None,
        channel_chat_id: str | None = None,
        channel_thread_id: str = "",
        channel_user_id: str | None = None,
        channel_message_id: str | None = None,
        request_id: str | None = None,
    ) -> ChatbotResult:
        """Prepare context, execute the agent, and persist its answer."""

        channel_name = channel or "web"
        request_started = perf_counter()

        common_fields = {
            "event": "chat_request_started",
            "request_id": request_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "channel": channel_name,
        }

        logger.info(
            "Chat request started",
            extra=common_fields,
        )

        # Step 1: Prepare conversation context.
        context_started = perf_counter()

        try:
            context = self.context_builder.build(
                message=message,
                conversation_id=conversation_id,
                user_id=user_id,
                channel=channel_name,
                channel_chat_id=channel_chat_id,
                channel_thread_id=channel_thread_id,
                channel_user_id=channel_user_id,
                channel_message_id=channel_message_id,
            )

            logger.info(
                "Chat context prepared",
                extra={
                    "event": "chat_context_prepared",
                    "request_id": request_id,
                    "conversation_id": context.conversation_id,
                    "user_id": user_id,
                    "channel": channel_name,
                    "user_message_id": context.user_message_id,
                    "history_count": context.history_count,
                    "duration_ms": round(
                        (perf_counter() - context_started) * 1000,
                        2,
                    ),
                },
            )

        except Exception:
            logger.exception(
                "Failed to prepare chat context",
                extra={
                    "event": "chat_context_failed",
                    "request_id": request_id,
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "channel": channel_name,
                    "duration_ms": round(
                        (perf_counter() - context_started) * 1000,
                        2,
                    ),
                },
            )
            raise

        # Step 2: Execute the AI agent and tools.
        agent_started = perf_counter()

        try:
            execution_result: AgentExecutionResult = (
                self.agent_executor.invoke(
                    messages=context.messages,
                    conversation_id=context.conversation_id,
                )
            )

            logger.info(
                "Agent execution completed",
                extra={
                    "event": "agent_execution_completed",
                    "request_id": request_id,
                    "conversation_id": context.conversation_id,
                    "user_id": user_id,
                    "channel": channel_name,
                    "tool_count": len(execution_result.tool_calls),
                    "answer_length": len(execution_result.answer),
                    "duration_ms": round(
                        (perf_counter() - agent_started) * 1000,
                        2,
                    ),
                },
            )

        except Exception:
            logger.exception(
                "Agent execution failed",
                extra={
                    "event": "agent_execution_failed",
                    "request_id": request_id,
                    "conversation_id": context.conversation_id,
                    "user_id": user_id,
                    "channel": channel_name,
                    "duration_ms": round(
                        (perf_counter() - agent_started) * 1000,
                        2,
                    ),
                },
            )
            raise

        # Step 3: Persist the final assistant answer.
        persistence_started = perf_counter()

        try:
            assistant_message = (
                self.conversation_service.save_assistant_message(
                    conversation_id=context.conversation_id,
                    content=execution_result.answer,
                )
            )

            assistant_message_id = str(assistant_message["id"])
        except Exception:
            logger.exception(
                "Failed to persist assistant answer",
                extra={
                    "event": "assistant_answer_persistence_failed",
                    "request_id": request_id,
                    "conversation_id": context.conversation_id,
                    "user_id": user_id,
                    "channel": channel_name,
                    "duration_ms": round(
                        (perf_counter() - persistence_started) * 1000,
                        2,
                    ),
                },
            )
            raise

        # Step 4: Build the result returned to the caller.
        result = ChatbotResult(
            conversation_id=context.conversation_id,
            answer=execution_result.answer,
            tool_calls=execution_result.tool_calls,
            user_message_id=context.user_message_id,
            assistant_message_id=assistant_message_id,
            channel_conversation_id=context.channel_conversation_id,
        )

        logger.info(
            "Chat request completed",
            extra={
                "event": "chat_request_completed",
                "request_id": request_id,
                "conversation_id": result.conversation_id,
                "user_id": user_id,
                "channel": channel_name,
                "assistant_message_id": result.assistant_message_id,
                "tool_count": len(result.tool_calls),
                "duration_ms": round(
                    (perf_counter() - request_started) * 1000,
                    2,
                ),
            },
        )

        return result
