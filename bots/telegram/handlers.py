import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bots.telegram.api_client import ProductApiClient


logger = logging.getLogger(__name__)

TELEGRAM_CHANNEL = "telegram"
TELEGRAM_MAX_MESSAGE_LENGTH = 4000


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None:
        return

    await update.message.reply_text(
        "Hello! I'm your Product Assistant.\n\n"
        "You can ask me about:\n"
        "- Product prices\n"
        "- Product specifications\n"
        "- Product availability\n"
        "- Stock information\n\n"
        "Send me a question to get started."
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None:
        return

    await update.message.reply_text(
        "Ask me anything about the products in the catalog.\n\n"
        "Examples:\n"
        "- What is the price of ASUS TUF Gaming A15?\n"
        "- Find ASUS laptops with 16 GB RAM.\n"
        "- How many ASUS laptops are in stock?"
    )


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.message

    if message is None or not message.text:
        return

    chat = update.effective_chat
    user = update.effective_user

    if chat is None or user is None:
        logger.warning(
            "Cannot process Telegram message without chat/user information"
        )
        return

    api_client: ProductApiClient = context.application.bot_data["api"]

    payload = {
        "message": message.text,
        "channel": TELEGRAM_CHANNEL,
        "channel_chat_id": str(chat.id),
        "channel_thread_id": str(message.message_thread_id or ""),
        "channel_user_id": str(user.id),
        "channel_message_id": str(message.message_id),
    }

    try:
        await message.chat.send_action(ChatAction.TYPING)

        result = await api_client.post(
            "/chat",
            json=payload,
        )

        answer = result.get("answer")

        if not isinstance(answer, str) or not answer.strip():
            answer = "Sorry, I couldn't generate an answer."

        assistant_message_id = result.get("assistant_message_id")
        channel_conversation_id = result.get("channel_conversation_id")

        # Split long responses into Telegram-sized messages.
        chunks = [
            answer[index:index + TELEGRAM_MAX_MESSAGE_LENGTH]
            for index in range(0, len(answer), TELEGRAM_MAX_MESSAGE_LENGTH)
        ]

        for chunk in chunks:
            sent_message = await message.reply_text(chunk)

            # Save the external Telegram message ID only after sending succeeds.
            if assistant_message_id and channel_conversation_id is not None:
                try:
                    await api_client.post(
                        "/channel-messages/delivery",
                        json={
                            "internal_message_id": assistant_message_id,
                            "channel_conversation_id": channel_conversation_id,
                            "channel_message_id": str(sent_message.message_id),
                            "channel": TELEGRAM_CHANNEL,
                            "delivery_status": "sent",
                        },
                    )
                except Exception:
                    # The Telegram reply was already sent.
                    # Log the mapping failure without sending a duplicate reply.
                    logger.exception(
                        "Telegram reply sent, but delivery mapping failed: "
                        "chat_id=%s, telegram_message_id=%s, "
                        "assistant_message_id=%s",
                        chat.id,
                        sent_message.message_id,
                        assistant_message_id,
                    )

            elif not assistant_message_id or channel_conversation_id is None:
                logger.warning(
                    "Cannot save Telegram delivery mapping: "
                    "assistant_message_id or channel_conversation_id is missing"
                )

    except Exception:
        logger.exception(
            "Failed to process Telegram message: chat_id=%s, user_id=%s",
            chat.id,
            user.id,
        )

        await message.reply_text(
            "Sorry, I couldn't process your request. "
            "Please try again later."
        )


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    logger.error(
        "Unhandled Telegram update error",
        exc_info=context.error,
    )


def register_handlers(application: Application) -> None:
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    application.add_error_handler(error_handler)
