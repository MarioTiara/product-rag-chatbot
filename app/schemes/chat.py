from pydantic import BaseModel, Field


from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None

    channel: str | None = None
    channel_chat_id: str | None = None
    channel_thread_id: str = ""
    channel_user_id: str | None = None
    channel_message_id: str | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    assistant_message_id: str
    channel_conversation_id: int | None = None