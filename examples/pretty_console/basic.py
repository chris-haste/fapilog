"""Example: Human-readable pretty console output."""

from fapilog import get_logger

logger = get_logger(format="pretty")

logger.info("Application started", env="local", version="1.0.0")
logger.warning("High memory usage", percent=85, threshold=80)
