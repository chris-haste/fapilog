"""
Basic usage example for fapilog v3.

This example demonstrates the core async-first logging functionality
with zero-copy operations and parallel processing.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fapilog import AsyncLogger, UniversalSettings
from fapilog.core.settings import LogLevel


async def main() -> None:
    """Demonstrate basic fapilog v3 usage."""

    # Configure async-first logging
    settings = UniversalSettings(
        level=LogLevel.INFO,
        sinks=["stdout"],
        async_processing=True,
        zero_copy_operations=True,
        parallel_processing=True,
        max_workers=2,
    )

    # Create async logger
    logger = await AsyncLogger.create(settings)
    async with logger as logger:
        # Log with rich metadata
        await logger.info(
            "Application started",
            source="example",
            category="system",
            tags={"environment": "development"},
            metrics={"startup_time": 0.5},
        )

        # Log different levels
        await logger.debug("Debug message")
        await logger.info("Info message")
        await logger.warning("Warning message")
        await logger.error("Error message")
        await logger.critical("Critical message")

        # Log with custom context
        await logger.info(
            "User action performed",
            source="api",
            category="business",
            tags={"user_id": "12345", "action": "login"},
            context={"ip_address": "192.168.1.1", "user_agent": "Mozilla/5.0"},
            metrics={"response_time": 0.15},
        )

        print("✅ Basic fapilog v3 example completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
