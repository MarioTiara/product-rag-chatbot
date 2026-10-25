from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class TelegramBotConfig:
    token: str
    api_url: str
    auth_username: str
    auth_password: str
    request_timeout: float = 60.0

    @classmethod
    def from_env(cls) -> "TelegramBotConfig":
        values = {
            "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN"),
            "API_AUTH_USERNAME": os.getenv("API_AUTH_USERNAME"),
            "API_AUTH_PASSWORD": os.getenv("API_AUTH_PASSWORD"),
        }

        missing = [
            key for key, value in values.items() if not value
        ]
        if missing:
            raise ValueError(
                f"Missing environment variables: {', '.join(missing)}"
            )

        return cls(
            token=values["TELEGRAM_BOT_TOKEN"],
            api_url=os.getenv(
                "PRODUCT_API_URL",
                "http://127.0.0.1:8000",
            ).rstrip("/"),
            auth_username=values["API_AUTH_USERNAME"],
            auth_password=values["API_AUTH_PASSWORD"],
        )