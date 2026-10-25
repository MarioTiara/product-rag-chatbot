from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import (
    get_conversation_service,
    get_current_user,
)
from app.schemes.channel_message import ChannelDeliveryRequest, ChannelDeliveryResponse
from app.services.conversation_service import ConversationService


router = APIRouter(
    prefix="/channel-messages",
    tags=["Channel Messages"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "/delivery",
    response_model=ChannelDeliveryResponse,
    status_code=status.HTTP_200_OK,
)
def record_channel_delivery(
    payload: ChannelDeliveryRequest,
    service: ConversationService = Depends(
        get_conversation_service
    ),
) -> ChannelDeliveryResponse:
    try:
        service.save_channel_message(
            internal_message_id=payload.internal_message_id,
            channel_conversation_id=payload.channel_conversation_id,
            channel_message_id=payload.channel_message_id,
            message_type="assistant",
            delivery_status=payload.delivery_status,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return ChannelDeliveryResponse(
        success=True,
        message="Channel message delivery recorded successfully.",
        internal_message_id=payload.internal_message_id,
        channel_conversation_id=payload.channel_conversation_id,
        channel_message_id=payload.channel_message_id,
        channel=payload.channel,
        delivery_status=payload.delivery_status,
    )