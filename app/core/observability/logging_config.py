
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any

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


def setup_logging(
    log_level: str | None = None,
    log_file: str | Path | None = None,
) -> None:
    """Configure JSON console logging and daily log-file rotation."""

    configured_level = (
        log_level or os.getenv("LOG_LEVEL", "INFO")
    ).upper()

    level = getattr(logging, configured_level, logging.INFO)

    # Resolve the configured log file.
    log_path = Path(
        log_file or os.getenv("LOG_FILE", "logs/app.log")
    ).expanduser()

    # Create the parent directory if it does not exist.
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    formatter = JsonFormatter()

    # Configure existing handlers without adding duplicates.
    for handler in root_logger.handlers:
        _configure_handler(handler, level, formatter)

    # Ensure a console handler exists.
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

    # Ensure the daily rotating file handler exists.
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
        # Remove an old observability file handler if its path changed.
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
    logging.getLogger("uvicorn.access").setLevel(
        logging.WARNING
    )
