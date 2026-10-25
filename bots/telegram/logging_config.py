import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(
    log_dir: Path | None = None,
    log_filename: str = "telegram_bot.log",
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
    level: int = logging.INFO,
) -> None:
    """Configure console and rotating file logging for the Telegram bot."""

    if log_dir is None:
        # Resolve the project root from this module's location.
        project_root = Path(__file__).resolve().parents[2]
        log_dir = project_root / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / log_filename

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid duplicate handlers when setup_logging is called repeatedly.
    if any(
        getattr(handler, "_telegram_logging_handler", False)
        for handler in root_logger.handlers
    ):
        return

    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    file_handler._telegram_logging_handler = True

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    console_handler._telegram_logging_handler = True

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
