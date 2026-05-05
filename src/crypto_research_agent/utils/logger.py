import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging():
    """Configure root logger with console and rotating file handlers."""
    root = logging.getLogger()
    if root.handlers:
        return  # Already configured

    root.setLevel(logging.DEBUG)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
    root.addHandler(console)

    try:
        os.makedirs("output/logs", exist_ok=True)
        file_handler = RotatingFileHandler(
            "output/logs/agent.log", maxBytes=10 * 1024 * 1024, backupCount=3
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
        )
        root.addHandler(file_handler)
    except (OSError, PermissionError):
        pass  # File logging unavailable — console logging still works


def get_logger(name: str) -> logging.Logger:
    """Get a named logger, setting up logging if not already done."""
    setup_logging()
    return logging.getLogger(name)
