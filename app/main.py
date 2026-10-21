
import logging

from fastapi import FastAPI

from app.api.routers import  health, products, chat
from app.configs.config import get_settings
from app.configs.logging_config import configure_logging



settings = get_settings()

configure_logging(settings.log_level, settings.log_file)
logging.getLogger(__name__).info(
    "logging configured level=%s file=%s",
    settings.log_level.upper(),
    settings.log_file,
)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="API for product lookup, search, stock, and price retrieval.",
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(products.router)
