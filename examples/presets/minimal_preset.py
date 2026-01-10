"""Example: Using the 'minimal' preset for backwards compatibility.

The minimal preset matches the default get_logger() behavior:
- INFO log level
- stdout JSON output only
- Default enrichers
- No file logging
- No redaction

Use this when migrating existing code or when you want explicit
preset selection while maintaining current behavior.
"""

from fapilog import get_logger

# These two are equivalent:
logger1 = get_logger(preset="minimal")
logger2 = get_logger()  # Same behavior

# Use the logger
logger1.info("Using minimal preset explicitly")
logger2.info("Using default behavior")

# Both produce identical output structure
logger1.info(
    "User action",
    user_id="123",
    action="click",
    target="button",
)
