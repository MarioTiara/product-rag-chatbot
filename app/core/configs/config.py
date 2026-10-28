
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root directory
BASE_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: SecretStr
    openai_model: str = "gpt-4.1-mini"

    # Database
    database_path: Path = BASE_DIR / "data" / "products.sqlite3"

    # Application
    app_name: str = "Product RAG Chatbot"
    app_version: str = "0.1.0"
    app_env: Literal["development", "production"] = "development"
    log_level: str = "INFO"
    log_file: Path = BASE_DIR / "logs" / "app.log"

    # Authentication / JWT
    jwt_secret_key: SecretStr
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = 30

    # Development user
    dev_user_id: str = "dev-user-001"
    dev_username: str = "dev-user"
    dev_password_hash: SecretStr
    dev_user_active: bool = True

    # Price conversion
    price_source_currency: str = "USD"
    price_target_currency: str = "IDR"
    price_conversion_rate: float = 17987.0

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
