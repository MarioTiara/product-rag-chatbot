from __future__ import annotations

from app.core.constants.constant import (
    VALID_DELIVERY_STATUSES,
    VALID_MESSAGE_TYPES,
)
from app.database.repositories.channel_message_repository import (
    ChannelMessageRepository,
)


class ChannelMessageService:
    def __init__(
        self,
        repository: ChannelMessageRepository | None = None,
    ) -> None:
        self.repository = repository or ChannelMessageRepository()

    def save_channel_message(
        self,
        *,
        internal_message_id: str,
        channel_conversation_id: int,
        channel_message_id: str,
        message_type: str,
        delivery_status: str,
    ) -> int:
        """Save an internal-to-external message mapping."""

        if not internal_message_id.strip():
            raise ValueError("internal_message_id must not be empty")

        if channel_conversation_id < 1:
            raise ValueError("channel_conversation_id must be positive")

        if not channel_message_id.strip():
            raise ValueError("channel_message_id must not be empty")

        if message_type not in VALID_MESSAGE_TYPES:
            raise ValueError(
                f"Unsupported message_type: {message_type}"
            )

        if delivery_status not in VALID_DELIVERY_STATUSES:
            raise ValueError(
                f"Unsupported delivery_status: {delivery_status}"
            )

        return self.repository.create(
            internal_message_id=internal_message_id,
            channel_conversation_id=channel_conversation_id,
            channel_message_id=channel_message_id,
            message_type=message_type,
            delivery_status=delivery_status,
        )

    def map_incoming_message(
        self,
        *,
        internal_message_id: str,
        channel_conversation_id: int,
        channel_message_id: str | None,
    ) -> int | None:
        """Map an incoming external user message."""

        if channel_message_id is None:
            return None

        return self.save_channel_message(
            internal_message_id=internal_message_id,
            channel_conversation_id=channel_conversation_id,
            channel_message_id=channel_message_id,
            message_type="user",
            delivery_status="received",
        )