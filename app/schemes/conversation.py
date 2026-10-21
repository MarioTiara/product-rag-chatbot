
from pydantic import BaseModel

from app.models.conversation import Conversation, ConversationMessage


class ConversationHistoryResponse(BaseModel):
    conversation: Conversation
    messages: list[ConversationMessage]