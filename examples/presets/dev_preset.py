"""Example: Using the 'dev' preset for local development.

The dev preset is optimized for local development with:
- DEBUG log level (see all messages)
- Immediate flushing (batch_size=1)
- Internal diagnostics enabled
- No redaction (safe for local dev)
"""

from fapilog import get_logger

# Create a logger with the dev preset
logger = get_logger(preset="dev")

# All log levels are visible
logger.debug("This debug message is visible")
logger.info("Application starting", version="1.0.0")
logger.warning("Configuration not found, using defaults")
logger.error("Failed to connect to cache", retry_in=5)

# Sensitive data is NOT redacted in dev (be careful with real secrets)
logger.info("User authenticated", user_id="123", api_key="dev-key-123")
