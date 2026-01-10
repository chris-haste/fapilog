"""Example: Using the 'production' preset for production deployments.

The production preset is optimized for production with:
- INFO log level
- File rotation (50MB, 10 files, compressed)
- Automatic redaction of sensitive fields
- Optimized batching (batch_size=100)
- No log drops under pressure (drop_on_full=False)
"""

from fapilog import get_logger

# Create a logger with the production preset
# This will create a ./logs directory for file output
logger = get_logger(preset="production")

# INFO and above are logged
logger.info("Service started", version="2.1.0", environment="production")
logger.warning("High memory usage detected", usage_percent=85)
logger.error("Payment processing failed", order_id="ORD-456")

# Sensitive fields are automatically redacted
# These fields are masked: password, api_key, token, secret, authorization,
#                          api_secret, private_key, ssn, credit_card
logger.info(
    "User login attempt",
    username="alice",
    password="super-secret-123",  # Will be redacted to "***"
    api_key="sk-live-abc123",  # Will be redacted to "***"
)

logger.info(
    "Payment processed",
    user_id="u-789",
    credit_card="4111-1111-1111-1111",  # Will be redacted to "***"
    amount=99.99,
)
