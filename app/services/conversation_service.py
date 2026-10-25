from __future__ import annotations

import logging
from typing import Any

from app.database.repositories.user_repository import UserRepository
from app.database.repositories.channel_identity_repository import (
    ChannelIdentityRepository,
)
from app.database.repositories.channel_message_repository import (
    ChannelMessageRepository,
)
from app.database.repositories.conversation_repository import (
    ConversationRepository,
)

from app.services.channel_identity_service import ChannelIdentityService
from app.services.channel_message_service import ChannelMessageService
from app.services.conversation_lifecycle_service import (
    ConversationLifecycleService,
)
from app.services.message_service import MessageService

logger = logging.getLogger(__name__)


class ConversationService:
    """Coordinate conversation, message, and channel workflows."""

    def __init__(
        self,
        conversation_repository: ConversationRepository | None = None,
        user_repository: UserRepository | None = None,
        channel_identity_repository: (
            ChannelIdentityRepository | None
        ) = None,
        channel_message_repository: (
            ChannelMessageRepository | None
        ) = None,
        history_limit: int = 12,
    ) -> None:
        if history_limit < 1:
            raise ValueError("history_limit must be at least 1")

        # Keep repository instances shared between relevant services.
        self.conversations = (
            conversation_repository or ConversationRepository()
        )
        self.users = user_repository or UserRepository()
        self.channel_identities = (
            channel_identity_repository
            or ChannelIdentityRepository()
        )
        self.channel_messages = (
            channel_message_repository
            or ChannelMessageRepository()
        )

        self.lifecycle = ConversationLifecycleService(
            repository=self.conversations,
        )
        self.messages = MessageService(
            repository=self.conversations,
            history_limit=history_limit,
        )
        self.identities = ChannelIdentityService(
            repository=self.channel_identities,
        )
        self.channel_message_service = ChannelMessageService(
            repository=self.channel_messages,
        )

        self.history_limit = history_limit

    # =========================================================
    # Main workflow
    # =========================================================

    def prepare_message(
        self,
        *,
        message: str,
        channel: str | None = None,
        channel_chat_id: str | None = None,
        channel_thread_id: str = "",
        channel_user_id: str | None = None,
        channel_message_id: str | None = None,
        conversation_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Resolve the conversation, load history, persist the user
        message, and map it to the external channel message if needed.
        """

        channel_conversation = None

        if channel is not None:
            user_id = self.identities.resolve_user_id(
                channel=channel,
                channel_user_id=channel_user_id,
                user_id=user_id,
            )

            conversation, channel_conversation = (
                self.lifecycle.resolve_channel_conversation(
                    message=message,
                    channel=channel,
                    channel_chat_id=channel_chat_id,
                    channel_thread_id=channel_thread_id,
                    user_id=user_id,
                )
            )
        else:
            conversation = self.lifecycle.resolve_api_conversation(
                message=message,
                conversation_id=conversation_id,
                user_id=user_id,
            )

        conversation_id = conversation["id"]

        # Important: load prior history before saving the current message.
        history = self.messages.get_history(
            conversation_id=conversation_id,
        )

        user_message = self.messages.save_user_message(
            conversation_id=conversation_id,
            content=message,
        )

        channel_message_record_id = None

        if (
            channel_conversation is not None
            and channel_message_id is not None
        ):
            channel_message_record_id = (
                self.channel_message_service.map_incoming_message(
                    internal_message_id=user_message["id"],
                    channel_conversation_id=channel_conversation["id"],
                    channel_message_id=channel_message_id,
                )
            )

        logger.debug(
            "Message prepared: conversation_id=%s, "
            "user_message_id=%s, channel_conversation_id=%s",
            conversation_id,
            user_message["id"],
            (
                channel_conversation["id"]
                if channel_conversation is not None
                else None
            ),
        )

        return {
            "conversation_id": conversation_id,
            "channel_conversation_id": (
                channel_conversation["id"]
                if channel_conversation is not None
                else None
            ),
            "user_message_id": user_message["id"],
            "channel_message_record_id": channel_message_record_id,
            "history": history,
            "conversation": conversation,
        }

    # =========================================================
    # Message persistence — public facade methods
    # =========================================================

    def save_assistant_message(
        self,
        *,
        conversation_id: str,
        content: str,
        tool_calls_json: str | None = None,
    ) -> dict[str, Any]:
        return self.messages.save_assistant_message(
            conversation_id=conversation_id,
            content=content,
            tool_calls_json=tool_calls_json,
        )

    def save_tool_call_message(
        self,
        *,
        conversation_id: str,
        tool_calls_json: str,
    ) -> dict[str, Any]:
        return self.messages.save_tool_call_message(
            conversation_id=conversation_id,
            tool_calls_json=tool_calls_json,
        )

    def save_tool_result(
        self,
        *,
        conversation_id: str,
        content: str,
        tool_call_id: str,
        tool_name: str,
    ) -> dict[str, Any]:
        return self.messages.save_tool_result(
            conversation_id=conversation_id,
            content=content,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
        )

    # =========================================================
    # Channel message persistence — public facade method
    # =========================================================

    def save_channel_message(
        self,
        *,
        internal_message_id: str,
        channel_conversation_id: int,
        channel_message_id: str,
        message_type: str,
        delivery_status: str,
    ) -> int:
        return self.channel_message_service.save_channel_message(
            internal_message_id=internal_message_id,
            channel_conversation_id=channel_conversation_id,
            channel_message_id=channel_message_id,
            message_type=message_type,
            delivery_status=delivery_status,
        )

    # Optional backward compatibility for existing callers.
    def save_channel_message_mapping(
        self,
        *,
        internal_message_id: str,
        channel_conversation_id: int,
        channel_message_id: str,
        message_type: str,
        delivery_status: str,
    ) -> int:
        return self.save_channel_message(
            internal_message_id=internal_message_id,
            channel_conversation_id=channel_conversation_id,
            channel_message_id=channel_message_id,
            message_type=message_type,
            delivery_status=delivery_status,
        )

    # =========================================================
    # Public history API
    # =========================================================

    def get_conversation_history(
        self,
        *,
        conversation_id: str,
        user_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        # Verify existence and ownership before retrieving messages.
        self.lifecycle.get_conversation(
            conversation_id=conversation_id,
            user_id=user_id,
        )

        return self.messages.get_history(
            conversation_id=conversation_id,
            limit=limit,
        )