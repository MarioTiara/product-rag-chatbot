
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.agents.prompts.prompt import SYSTEM_PROMPT
from app.agents.schemes.chat_context import ChatContext
from app.services.conversation_service import ConversationService
from app.agents.utils.message_mapper import MessageMapper




class ChatContextBuilder:
    """Build the conversation context and AI-ready messages."""

    def __init__(
        self,
        conversation_service: ConversationService,
        message_mapper: MessageMapper,
    ) -> None:
        self.conversation_service = conversation_service
        self.message_mapper = message_mapper

    def build(
        self,
        message: str,
        *,
        conversation_id: str | None = None,
        user_id: str | None = None,
        channel: str = "web",
        channel_chat_id: str | None = None,
        channel_thread_id: str = "",
        channel_user_id: str | None = None,
        channel_message_id: str | None = None,
    ) -> ChatContext:
        """Prepare conversation history and construct AI messages."""

        context = self.conversation_service.prepare_message(
            message=message,
            conversation_id=conversation_id,
            user_id=user_id,
            channel=channel,
            channel_chat_id=channel_chat_id,
            channel_thread_id=channel_thread_id,
            channel_user_id=channel_user_id,
            channel_message_id=channel_message_id,
        )

        history = context["history"]

        history_messages = (
            self.message_mapper.records_to_openai_messages(history)
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *history_messages,
            {"role": "user", "content": message},
        ]

        return ChatContext(
            conversation_id=context["conversation_id"],
            user_message_id=context["user_message_id"],
            channel_conversation_id=context.get(
                "channel_conversation_id"
            ),
            messages=messages,
            history_count=len(history),
        )
