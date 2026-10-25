import logging
import sys

from app.core.config import get_settings


def configure_logging() -> logging.Logger:
    """Configure structured application logging in English."""
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    logger = logging.getLogger("cogniflow")
    logger.setLevel(log_level)
    logger.info(
        "Logging initialized for '%s' in '%s' mode.",
        settings.app_name,
        settings.app_env,
    )
    return logger

