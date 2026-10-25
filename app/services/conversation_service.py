
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

logger = logging.getLogger(__name__)


class ConversationService:
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
        Resolve a conversation, load previous history,
        save the incoming user message, and optionally map
        it to an external channel message.
        """
        logger.debug(
            "Preparing message: channel=%s, chat_id=%s, "
            "thread_id=%s, conversation_id=%s",
            channel,
            channel_chat_id,
            channel_thread_id,
            conversation_id,
        )

        channel_conversation = None

        # 1. Resolve the conversation.
        if channel is not None:
            user_id = self._resolve_channel_user(
                channel=channel,
                channel_user_id=channel_user_id,
                user_id=user_id,
            )

            conversation, channel_conversation = (
                self._resolve_channel_conversation(
                    message=message,
                    channel=channel,
                    channel_chat_id=channel_chat_id,
                    channel_thread_id=channel_thread_id,
                    user_id=user_id,
                )
            )

            conversation_id = conversation["id"]

        else:
            conversation = self._resolve_api_conversation(
                message=message,
                conversation_id=conversation_id,
                user_id=user_id,
            )
            conversation_id = conversation["id"]

        # 2. Retrieve history BEFORE saving the current message.
        history = self._get_history_before_message(
            conversation_id=conversation_id,
        )

        # 3. Save the incoming user message.
        user_message = self._save_user_message(
            conversation_id=conversation_id,
            content=message,
        )

        # 4. Map the internal message to the external channel ID.
        channel_message_record_id = (
            self._map_incoming_channel_message(
                user_message=user_message,
                channel_conversation=channel_conversation,
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

    def save_channel_message(
        self,
        *,
        internal_message_id: str,
        channel_conversation_id: int,
        channel_message_id: str,
        message_type: str,
        delivery_status: str,
    ) -> int:
        """Persist a mapping between an internal and external channel message."""

        if not internal_message_id.strip():
            raise ValueError("internal_message_id must not be empty")

        if channel_conversation_id < 1:
            raise ValueError("channel_conversation_id must be positive")

        if not channel_message_id.strip():
            raise ValueError("channel_message_id must not be empty")

        if message_type not in {"user", "assistant"}:
            raise ValueError("message_type must be 'user' or 'assistant'")

        if delivery_status not in {
            "received",
            "pending",
            "sent",
            "failed",
        }:
            raise ValueError("Invalid delivery_status")

        return self.channel_messages.create(
            internal_message_id=internal_message_id,
            channel_conversation_id=channel_conversation_id,
            channel_message_id=channel_message_id,
            message_type=message_type,
            delivery_status=delivery_status,
        )
    # =========================================================
    # User and channel validation
    # =========================================================

    def _validate_channel(
        self,
        *,
        channel: str,
        channel_chat_id: str | None,
    ) -> None:
        """Validate the channel name and external chat ID."""
        if channel not in self.conversations.VALID_CHANNELS:
            raise ValueError(f"Unsupported channel: {channel}")

        if not channel_chat_id:
            raise ValueError(
                "channel_chat_id is required for channel requests"
            )

    def _resolve_channel_user(
        self,
        *,
        channel: str,
        channel_user_id: str | None,
        user_id: str | None,
    ) -> str | None:
        """Resolve an internal user from a linked channel identity."""
        if user_id is not None or channel_user_id is None:
            return user_id

        identity = self.channel_identities.get_by_channel_user(
            channel=channel,
            channel_user_id=channel_user_id,
        )

        if identity is None:
            logger.debug(
                "No linked identity: channel=%s, channel_user_id=%s",
                channel,
                channel_user_id,
            )
            return None

        logger.debug(
            "Resolved channel identity to user_id=%s",
            identity["user_id"],
        )
        return identity["user_id"]

    def _validate_conversation_ownership(
        self,
        *,
        conversation: dict[str, Any],
        user_id: str | None,
        allow_unowned: bool = False,
    ) -> None:
        """Prevent a user from accessing another user's conversation."""
        owner_id = conversation.get("user_id")

        if user_id is None:
            return

        if owner_id == user_id:
            return

        if allow_unowned and owner_id is None:
            return

        raise PermissionError(
            "Conversation does not belong to this user"
        )

    # =========================================================
    # Channel conversation resolution
    # =========================================================

    def _resolve_channel_conversation(
        self,
        *,
        message: str,
        channel: str,
        channel_chat_id: str | None,
        channel_thread_id: str,
        user_id: str | None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Return (conversation, channel_conversation).

        Create the internal conversation before its channel mapping
        when no mapping exists.
        """
        self._validate_channel(
            channel=channel,
            channel_chat_id=channel_chat_id,
        )

        logger.debug(
            "Looking up channel conversation: "
            "channel=%s, chat_id=%s, thread_id=%s",
            channel,
            channel_chat_id,
            channel_thread_id,
        )

        channel_conversation = (
            self.conversations.get_channel_conversation(
                channel=channel,
                channel_chat_id=channel_chat_id,
                channel_thread_id=channel_thread_id,
            )
        )

        if channel_conversation is not None:
            logger.debug(
                "Found channel mapping: mapping_id=%s, "
                "conversation_id=%s",
                channel_conversation.get("id"),
                channel_conversation.get("conversation_id"),
            )

            return self._load_mapped_conversation(
                channel_conversation=channel_conversation,
                user_id=user_id,
            )

        logger.debug(
            "No channel mapping found; creating conversation"
        )

        return self._create_channel_conversation(
            message=message,
            channel=channel,
            channel_chat_id=channel_chat_id,
            channel_thread_id=channel_thread_id,
            user_id=user_id,
        )

    def _load_mapped_conversation(
        self,
        *,
        channel_conversation: dict[str, Any],
        user_id: str | None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Load and validate the conversation referenced by a mapping."""
        conversation_id = channel_conversation["conversation_id"]

        conversation = self.conversations.get_conversation(
            conversation_id
        )

        if conversation is None:
            logger.error(
                "Orphaned channel mapping: mapping_id=%s, "
                "conversation_id=%s",
                channel_conversation.get("id"),
                conversation_id,
            )
            raise RuntimeError(
                "Channel mapping references a missing conversation "
                f"(mapping_id={channel_conversation.get('id')}, "
                f"conversation_id={conversation_id})"
            )

        self._validate_conversation_ownership(
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
        channel_chat_id: str | None,
        channel_thread_id: str,
        user_id: str | None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Create the internal conversation, then the channel mapping."""
        conversation = self.conversations.create_conversation(
            user_id=user_id,
            title=message[:80],
        )
        conversation_id = conversation["id"]

        logger.debug(
            "Created conversation: conversation_id=%s",
            conversation_id,
        )

        channel_conversation = (
            self.conversations.get_or_create_channel_conversation(
                conversation_id=conversation_id,
                channel=channel,
                channel_chat_id=channel_chat_id,
                channel_thread_id=channel_thread_id,
            )
        )

        logger.debug(
            "Resolved channel mapping: mapping_id=%s, "
            "conversation_id=%s",
            channel_conversation.get("id"),
            channel_conversation.get("conversation_id"),
        )

        # get_or_create may return a mapping created by another request.
        # Always load the conversation ID from the mapping itself.
        conversation, channel_conversation = (
            self._load_mapped_conversation(
                channel_conversation=channel_conversation,
                user_id=user_id,
            )
        )

        return conversation, channel_conversation

    # =========================================================
    # Web/API conversation resolution
    # =========================================================

    def _resolve_api_conversation(
        self,
        *,
        message: str,
        conversation_id: str | None,
        user_id: str | None,
    ) -> dict[str, Any]:
        """Create a new API conversation or load an existing one."""
        if conversation_id is None:
            conversation = self.conversations.create_conversation(
                user_id=user_id,
                title=message[:80],
            )

            logger.debug(
                "Created API conversation: conversation_id=%s",
                conversation["id"],
            )
            return conversation

        conversation = self.conversations.get_conversation(
            conversation_id
        )

        if conversation is None:
            raise ValueError("Conversation not found")

        self._validate_conversation_ownership(
            conversation=conversation,
            user_id=user_id,
        )

        return conversation

    # =========================================================
    # Message persistence
    # =========================================================

    def _get_history_before_message(
        self,
        *,
        conversation_id: str,
    ) -> list[dict[str, Any]]:
        """Retrieve recent history before adding the current user message."""
        logger.debug(
            "Loading history: conversation_id=%s, limit=%s",
            conversation_id,
            self.history_limit,
        )

        return self.conversations.get_history(
            conversation_id=conversation_id,
            limit=self.history_limit,
        )

    def _save_user_message(
        self,
        *,
        conversation_id: str,
        content: str,
    ) -> dict[str, Any]:
        """Persist the incoming user message."""
        user_message = self.conversations.create_message(
            conversation_id=conversation_id,
            role="user",
            content=content,
        )

        logger.debug(
            "Saved user message: conversation_id=%s, message_id=%s",
            conversation_id,
            user_message["id"],
        )
        return user_message

    def _map_incoming_channel_message(
        self,
        *,
        user_message: dict[str, Any],
        channel_conversation: dict[str, Any] | None,
        channel_message_id: str | None,
    ) -> int | None:
        """Map an incoming platform message to its internal message."""
        if channel_conversation is None or channel_message_id is None:
            return None

        return self.channel_messages.create(
            internal_message_id=user_message["id"],
            channel_conversation_id=channel_conversation["id"],
            channel_message_id=channel_message_id,
            message_type="user",
            delivery_status="received",
        )

    # =========================================================
    # Assistant and tool messages
    # =========================================================

    def save_assistant_message(
        self,
        *,
        conversation_id: str,
        content: str,
        tool_calls_json: str | None = None,
    ) -> dict[str, Any]:
        """Persist the assistant response."""
        return self.conversations.create_message(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            tool_calls_json=tool_calls_json,
        )

    def save_tool_call_message(
        self,
        *,
        conversation_id: str,
        tool_calls_json: str,
    ) -> dict[str, Any]:
        """Persist an assistant message containing tool calls."""
        return self.conversations.create_message(
            conversation_id=conversation_id,
            role="assistant",
            content="",
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
        """Persist a tool result."""
        return self.conversations.create_message(
            conversation_id=conversation_id,
            role="tool",
            content=content,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
        )

    # =========================================================
    # External channel message mapping
    # =========================================================

    def save_channel_message_mapping(
        self,
        *,
        internal_message_id: str,
        channel_conversation_id: int,
        channel_message_id: str,
        message_type: str,
        delivery_status: str,
    ) -> int:
        """Map an internal message to an external channel message."""
        return self.channel_messages.create(
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
        """Retrieve conversation history with optional ownership checks."""
        conversation = self.conversations.get_conversation(
            conversation_id
        )

        if conversation is None:
            raise ValueError("Conversation not found")

        self._validate_conversation_ownership(
            conversation=conversation,
            user_id=user_id,
        )

        effective_limit = (
            self.history_limit if limit is None else limit
        )

        if effective_limit < 1:
            raise ValueError("limit must be at least 1")

        return self.conversations.get_history(
            conversation_id=conversation_id,
            limit=effective_limit,
        )
