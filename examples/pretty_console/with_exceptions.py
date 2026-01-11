"""Example: Pretty output with exception tracebacks."""

from fapilog import get_logger

logger = get_logger(format="pretty")

try:
    _ = 1 / 0
except ZeroDivisionError:
    logger.exception("Computation failed", operation="divide")
