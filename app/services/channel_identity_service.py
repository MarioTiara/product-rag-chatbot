from __future__ import annotations

import logging

from app.core.constants.constant import VALID_CHANNELS
from app.database.repositories.channel_identity_repository import (
    ChannelIdentityRepository,
)

logger = logging.getLogger(__name__)


class ChannelIdentityService:
    def __init__(
        self,
        repository: ChannelIdentityRepository | None = None,
    ) -> None:
        self.repository = repository or ChannelIdentityRepository()

    def resolve_user_id(
        self,
        *,
        channel: str,
        channel_user_id: str | None,
        user_id: str | None = None,
    ) -> str | None:
        """Resolve an internal user ID from a channel identity."""

        if channel not in VALID_CHANNELS:
            raise ValueError(f"Unsupported channel: {channel}")

        # Explicit internal user ID takes precedence.
        if user_id is not None:
            return user_id

        # Anonymous or unlinked channel identity.
        if channel_user_id is None:
            return None

        identity = self.repository.get_by_channel_user(
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

        return identity["user_id"]