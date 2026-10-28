
import logging

from fastapi import FastAPI

from app.api.routers import (
    auth,
    channel_message,
    chat,
    health,
    products,
)
from app.core.configs.config import get_settings
from app.core.observability.logging_config import setup_logging
from app.core.observability.middleware import (
    register_observability_middleware,
)


settings = get_settings()

# Configure structured JSON logging.
setup_logging()

logger = logging.getLogger(__name__)
logger.info(
    "Logging configured",
    extra={
        "event": "logging_configured",
        "log_level": settings.log_level.upper(),
        "log_file": str(settings.log_file),
    },
)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "API for product lookup, search, stock, "
        "and price retrieval."
    ),
)

# Register middleware before including routers.
register_observability_middleware(app)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(products.router)
app.include_router(auth.router)
app.include_router(channel_message.router)
