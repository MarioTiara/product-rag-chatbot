
class AIAuthenticationError(RuntimeError):
    """Raised when an AI provider rejects its credentials."""


class ChatProviderAuthenticationError(RuntimeError):
    """Raised when the configured AI provider cannot authenticate."""
