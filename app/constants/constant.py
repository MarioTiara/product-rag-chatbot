VALID_CHANNELS = frozenset({
    "telegram",
    "whatsapp",
    "web",
})

VALID_MESSAGE_TYPES = frozenset({
    "user",
    "assistant",
})

VALID_DELIVERY_STATUSES = frozenset({
    "received",
    "pending",
    "sent",
    "failed",
})