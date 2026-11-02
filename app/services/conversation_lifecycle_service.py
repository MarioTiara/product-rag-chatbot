from __future__ import annotations

import logging
from typing import Any

from app.core.constants.constant import VALID_CHANNELS
from app.database.repositories.conversation_repository import (
    ConversationRepository,
)

logger = logging.getLogger(__name__)


class ConversationLifecycleService:
    def __init__(
        self,
        repository: ConversationRepository | None = None,
    ) -> None:
        self.repository = repository or ConversationRepository()

    def resolve_channel_conversation(
        self,
        *,
        message: str,
        channel: str,
        channel_chat_id: str | None,
        channel_thread_id: str = "",
        user_id: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Resolve an internal conversation and its channel mapping."""

        if channel not in VALID_CHANNELS:
            raise ValueError(f"Unsupported channel: {channel}")

        if not channel_chat_id:
            raise ValueError(
                "channel_chat_id is required for channel requests"
            )

        channel_conversation = self.repository.get_channel_conversation(
            channel=channel,
            channel_chat_id=channel_chat_id,
            channel_thread_id=channel_thread_id,
        )

        if channel_conversation is not None:
            return self._load_mapped_conversation(
                channel_conversation=channel_conversation,
                user_id=user_id,
            )

        return self._create_channel_conversation(
            message=message,
            channel=channel,
            channel_chat_id=channel_chat_id,
            channel_thread_id=channel_thread_id,
            user_id=user_id,
        )

    def resolve_api_conversation(
        self,
        *,
        message: str,
        conversation_id: str | None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new API conversation or load an existing one."""

        if conversation_id is None:
            return self.repository.create_conversation(
                user_id=user_id,
                title=message[:80],
            )

        conversation = self.repository.get_conversation(conversation_id)

        if conversation is None:
            raise ValueError("Conversation not found")

        self.validate_ownership(
            conversation=conversation,
            user_id=user_id,
        )

        return conversation

    def get_conversation(
        self,
        *,
        conversation_id: str,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Load a conversation and verify its ownership."""

        conversation = self.repository.get_conversation(conversation_id)

        if conversation is None:
            raise ValueError("Conversation not found")

        self.validate_ownership(
            conversation=conversation,
            user_id=user_id,
        )

        return conversation

    @staticmethod
    def validate_ownership(
        *,
        conversation: dict[str, Any],
        user_id: str | None,
        allow_unowned: bool = False,
    ) -> None:
        """Prevent access to a conversation owned by another user."""

        owner_id = conversation.get("user_id")

        if user_id is None or owner_id == user_id:
            return

        if allow_unowned and owner_id is None:
            return

        raise PermissionError(
            "Conversation does not belong to this user"
        )

    def _load_mapped_conversation(
        self,
        *,
        channel_conversation: dict[str, Any],
        user_id: str | None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        conversation_id = channel_conversation["conversation_id"]

        conversation = self.repository.get_conversation(conversation_id)

        if conversation is None:
            logger.error(
                "Orphaned channel mapping: mapping_id=%s, "
                "conversation_id=%s",
                channel_conversation.get("id"),
                conversation_id,
            )
            raise RuntimeError(
                "Channel mapping references a missing conversation"
            )

        self.validate_ownership(
            conversation=conversation,
            user_id=user_id,
            allow_unowned=True,
        )

        return conversation, channel_conversation

    def _create_channel_conversation(
        self,
        *,
        message: str,
        channel: str,
        channel_chat_id: str,
        channel_thread_id: str,
        user_id: str | None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        conversation = self.repository.create_conversation(
            user_id=user_id,
            title=message[:80],
        )

        channel_conversation = (
            self.repository.get_or_create_channel_conversation(
                conversation_id=conversation["id"],
                channel=channel,
                channel_chat_id=channel_chat_id,
                channel_thread_id=channel_thread_id,
            )
        )

        # The mapping may have been created by another concurrent request.
        # Always use the conversation referenced by the resolved mapping.
        return self._load_mapped_conversation(
            channel_conversation=channel_conversation,
            user_id=user_id,
        )