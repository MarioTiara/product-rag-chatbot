from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ChannelDeliveryRequest(BaseModel):
    internal_message_id: str = Field(..., min_length=1, max_length=36)
    channel_conversation_id: int = Field(..., gt=0)
    channel_message_id: str = Field(..., min_length=1, max_length=255)
    channel: Literal["telegram", "whatsapp", "web"]
    delivery_status: Literal["sent", "failed"]

    @field_validator("internal_message_id", "channel_message_id", mode="before")
    @classmethod
    def validate_message_ids(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("Message ID must be a string.")

        value = value.strip()

        if not value:
            raise ValueError("Message ID must not be empty.")

        return value
    

class ChannelDeliveryResponse(BaseModel):
    success: bool
    message: str
    internal_message_id: str
    channel_conversation_id: int
    channel_message_id: str
    channel: str
    delivery_status: str