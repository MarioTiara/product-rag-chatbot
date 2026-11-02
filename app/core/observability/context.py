
from __future__ import annotations

from contextvars import ContextVar, Token


request_id_var: ContextVar[str | None] = ContextVar(
    "request_id",
    default=None,
)

conversation_id_var: ContextVar[str | None] = ContextVar(
    "conversation_id",
    default=None,
)

channel_var: ContextVar[str | None] = ContextVar(
    "channel",
    default=None,
)


def set_conversation_context(
    *,
    conversation_id: str | None = None,
    channel: str | None = None,
) -> tuple[Token, Token]:
    """Bind conversation metadata to the current execution context."""

    conversation_token = conversation_id_var.set(conversation_id)
    channel_token = channel_var.set(channel)

    return conversation_token, channel_token


def reset_conversation_context(
    tokens: tuple[Token, Token],
) -> None:
    """Restore the previous execution context."""

    conversation_token, channel_token = tokens

    channel_var.reset(channel_token)
    conversation_id_var.reset(conversation_token)
