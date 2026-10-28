
class ConversationNotFoundError(Exception):
    """Raised when a conversation cannot be found."""

    def __init__(self, conversation_id: str) -> None:
        self.conversation_id = conversation_id
        super().__init__(
            f"Conversation '{conversation_id}' was not found."
        )