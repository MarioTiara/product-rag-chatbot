
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any

from app.core.configs.config import get_settings
from app.core.observability.context import (
    channel_var,
    conversation_id_var,
    request_id_var,
)


class ObservabilityFilter(logging.Filter):
    """Attach correlation context to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.conversation_id = conversation_id_var.get()
        record.channel = channel_var.get()
        return True


class JsonFormatter(logging.Formatter):
    """Serialize log records into structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": (
                datetime.fromtimestamp(
                    record.created,
                    timezone.utc,
                )
                .isoformat(timespec="milliseconds")
                .replace("+00:00", "Z")
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
            "conversation_id": getattr(
                record, "conversation_id", None
            ),
            "channel": getattr(record, "channel", None),
        }

        standard_fields = set(
            logging.makeLogRecord({}).__dict__.keys()
        )
        reserved_fields = standard_fields | {
            "message",
            "asctime",
            "request_id",
            "conversation_id",
            "channel",
        }

        for key, value in record.__dict__.items():
            if (
                key not in reserved_fields
                and not key.startswith("_")
            ):
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(
                record.exc_info
            )

        return json.dumps(
            payload,
            ensure_ascii=False,
            default=str,
        )


def _configure_handler(
    handler: logging.Handler,
    level: int,
    formatter: logging.Formatter,
) -> None:
    """Apply common settings to a logging handler."""

    handler.setLevel(level)
    handler.setFormatter(formatter)

    if not any(
        isinstance(item, ObservabilityFilter)
        for item in handler.filters
    ):
        handler.addFilter(ObservabilityFilter())


def setup_logging() -> None:
    """Configure JSON console logging and daily file rotation."""

    settings = get_settings()

    configured_level = settings.log_level.upper()
    level = getattr(logging, configured_level, None)

    if not isinstance(level, int):
        raise ValueError(
            f"Invalid LOG_LEVEL configuration: {settings.log_level}"
        )

    log_path = Path(settings.log_file).expanduser()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    formatter = JsonFormatter()

    # Configure existing handlers.
    for handler in root_logger.handlers:
        _configure_handler(handler, level, formatter)

    # Ensure one console handler exists.
    console_handler = next(
        (
            handler
            for handler in root_logger.handlers
            if getattr(
                handler, "_observability_handler_type", None
            ) == "console"
        ),
        None,
    )

    if console_handler is None:
        console_handler = logging.StreamHandler()
        console_handler._observability_handler_type = "console"
        root_logger.addHandler(console_handler)

    _configure_handler(console_handler, level, formatter)

    # Ensure one daily rotating file handler exists.
    resolved_log_path = str(log_path.resolve())

    file_handler = next(
        (
            handler
            for handler in root_logger.handlers
            if isinstance(handler, TimedRotatingFileHandler)
            and getattr(
                handler, "_observability_handler_type", None
            ) == "daily_file"
            and handler.baseFilename == resolved_log_path
        ),
        None,
    )

    if file_handler is None:
        # Remove the old observability file handler if the path changed.
        for handler in root_logger.handlers[:]:
            if getattr(
                handler, "_observability_handler_type", None
            ) == "daily_file":
                root_logger.removeHandler(handler)
                handler.close()

        file_handler = TimedRotatingFileHandler(
            filename=resolved_log_path,
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
            delay=False,
            utc=False,
        )
        file_handler._observability_handler_type = "daily_file"
        root_logger.addHandler(file_handler)

    _configure_handler(file_handler, level, formatter)

    # Reduce noisy third-party access logs.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
