import logging

from telegram.ext import Application

from bots.telegram.api_client import ProductApiClient
from bots.telegram.config import TelegramBotConfig
from bots.telegram.handlers import register_handlers


logging.basicConfig(level=logging.INFO)


async def post_init(application: Application) -> None:
    config = TelegramBotConfig.from_env()

    application.bot_data["api"] = ProductApiClient(config)
    logging.info("Product API client initialized")


async def post_shutdown(application: Application) -> None:
    api = application.bot_data.get("api")

    if api is not None:
        await api.close()


def main() -> None:
    config = TelegramBotConfig.from_env()

    application = (
        Application.builder()
        .token(config.token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    register_handlers(application)
    application.run_polling()


if __name__ == "__main__":
    main()