"""Example: Using the 'fastapi' preset for FastAPI applications.

The fastapi preset is optimized for async web applications with:
- INFO log level
- stdout JSON output (container-friendly)
- context_vars enricher for request context propagation
- Balanced batching (batch_size=50)
"""

import asyncio

from fapilog import get_async_logger


async def handle_request(request_id: str, user_id: str) -> None:
    """Simulate handling a web request."""
    # Create an async logger with the fastapi preset
    logger = await get_async_logger(preset="fastapi")

    # Log with request context
    await logger.info(
        "Request received",
        request_id=request_id,
        user_id=user_id,
        path="/api/users",
    )

    # Simulate some async work
    await asyncio.sleep(0.1)

    await logger.info(
        "Request completed",
        request_id=request_id,
        status=200,
        duration_ms=105,
    )


async def main() -> None:
    """Run example requests."""
    # Simulate concurrent requests
    await asyncio.gather(
        handle_request("req-001", "user-alice"),
        handle_request("req-002", "user-bob"),
        handle_request("req-003", "user-charlie"),
    )


if __name__ == "__main__":
    asyncio.run(main())
