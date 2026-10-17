
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root directory
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: SecretStr
    openai_model: str = "gpt-4.1-mini"

    # Database
    database_path: Path = BASE_DIR / "data" / "products.db"

    # Application
    app_name: str = "Product RAG Chatbot"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    log_file: Path = BASE_DIR / "logs" / "app.log"

    # Price conversion
    price_source_currency: str = "INR"
    price_target_currency: str = "IDR"
    price_conversion_rate: float = 190.0

    # Chat memory
    chat_history_limit: int = 12

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
