from __future__ import annotations

import logging
from pathlib import Path


def configure_logging(level_name: str, log_file: Path) -> None:
    console_level = getattr(logging, level_name.upper(), logging.INFO)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    for handler in root.handlers:
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(formatter)

    if not any(getattr(handler, "_product_rag_chatbot_file", False) for handler in root.handlers):
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        file_handler._product_rag_chatbot_file = True  # type: ignore[attr-defined]
        root.addHandler(file_handler)

    if not any(getattr(handler, "_product_rag_chatbot_stream", False) for handler in root.handlers):
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(console_level)
        stream_handler.setFormatter(formatter)
        stream_handler._product_rag_chatbot_stream = True  # type: ignore[attr-defined]
        root.addHandler(stream_handler)
