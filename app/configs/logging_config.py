
from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


def configure_logging(level_name: str, log_file: Path) -> None:
    console_level = getattr(logging, level_name.upper(), logging.INFO)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt=(
            "%(asctime)s | "
            "%(levelname)-8s | "
            "%(name)-30s | "
            "%(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    for handler in root.handlers:
        handler.setFormatter(formatter)

    if not any(
        getattr(handler, "_product_rag_chatbot_file", False)
        for handler in root.handlers
    ):
        file_handler = TimedRotatingFileHandler(
            filename=log_file,
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        file_handler.suffix = "%Y-%m-%d"
        file_handler._product_rag_chatbot_file = True  # type: ignore[attr-defined]
        root.addHandler(file_handler)

    if not any(
        getattr(handler, "_product_rag_chatbot_stream", False)
        for handler in root.handlers
    ):
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(console_level)
        stream_handler.setFormatter(formatter)
        stream_handler._product_rag_chatbot_stream = True  # type: ignore[attr-defined]
        root.addHandler(stream_handler)
