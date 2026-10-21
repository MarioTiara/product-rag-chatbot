
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
    if update.message is None or not update.message.text:
        return

    api_client: ProductApiClient = (
        context.application.bot_data["api"]
    )

    user_message = update.message.text

    payload = {
        "message": user_message,
    }

    try:
        await update.message.chat.send_action(
            ChatAction.TYPING
        )

        result = await api_client.post(
            "/chat",
            json=payload,
        )

        answer = result.get("answer")

        if not isinstance(answer, str) or not answer.strip():
            answer = "Sorry, I couldn't generate an answer."

        # Split long responses to stay within Telegram's message limit.
        max_length = 4000

        for start_index in range(0, len(answer), max_length):
            await update.message.reply_text(
                answer[start_index:start_index + max_length]
            )

    except Exception:
        logger.exception(
            "Failed to process Telegram message"
        )

        await update.message.reply_text(
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


def register_handlers(
    application: Application,
) -> None:
    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("help", help_command)
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    application.add_error_handler(error_handler)
