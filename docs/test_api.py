"""
Test API file to demonstrate @docs: markers.

This file shows how you would use the @docs: markers in your source code
to automatically generate formatted API documentation.
"""

from typing import Any, Dict, List, Optional


async def configure_logging(
    level: str = "INFO", format: str = "json", sinks: Optional[List[str]] = None
) -> None:
    """
    Configure the logging system with the specified settings.

    This function must be called before any logging operations can occur.
    It sets up sinks, processors, and enrichers based on the provided configuration.

    @docs:use_cases
    - **Development environments** need **human-readable logs** for debugging and troubleshooting
    - **Production systems** require **structured JSON logs** for log aggregation and analysis
    - **Security audits** demand **detailed logging** with configurable **sensitivity levels**
    - **High-throughput applications** benefit from **asynchronous logging** with backpressure protection

    @docs:examples
    ```python
    from fapilog import configure_logging, LoggingSettings

    # Basic configuration
    await configure_logging(level="DEBUG", format="pretty")

    # With custom sinks
    await configure_logging(
        level="INFO",
        format="json",
        sinks=["stdout", "file", "http"]
    )
    ```

    @docs:notes
    - All timestamps are emitted in **RFC3339 UTC format**
    - The configuration is **immutable** after initialization - changes require restart
    - See [Logging Levels](../concepts/logging-levels.md) for detailed level descriptions
    - Related: [Custom Sinks](../examples/custom-sinks.md), [Environment Configuration](../config.md)
    """
    pass


class Logger:
    """
    Main logging interface for fapilog applications.

    Provides async-first logging with enterprise-grade features including
    encryption, compliance, and observability capabilities.

    @docs:use_cases
    - **Web applications** need **request-scoped logging** with correlation IDs
    - **Microservices** require **distributed tracing** and **structured logging**
    - **Batch processing** benefits from **high-throughput** and **non-blocking operations**
    - **Security applications** demand **audit logging** with **immutable records**

    @docs:examples
    ```python
    from fapilog import get_async_logger

    # Create logger instance
    logger = await get_async_logger()

    # Basic logging
    await logger.info("Application started")
    await logger.error("Database connection failed", exc_info=True)

    # Structured logging with context
    await logger.info(
        "User action",
        user_id="12345",
        action="login",
        ip_address="192.168.1.1",
    )

    # Cleanup
    await logger.drain()
    ```

    @docs:notes
    - Logger instances are **not thread-safe** - create one per thread/coroutine
    - All methods are **async** and should be awaited
    - **Always call close()** when done to ensure proper cleanup
    - See [Async Logging](../concepts/async-logging.md) for best practices
    """

    async def info(self, message: str, **kwargs) -> None:
        """
        Log an informational message.

        @docs:use_cases
        - **General application events** like startup, shutdown, and status updates
        - **User actions** that should be tracked for analytics and debugging
        - **System health** monitoring and operational insights

        @docs:examples
        ```python
        await logger.info("Application started successfully")
        await logger.info("User logged in", user_id="12345")
        ```

        @docs:notes
        - Messages are processed asynchronously for high performance
        - Additional context can be passed via **kwargs
        - See [Log Levels](../concepts/log-levels.md) for level hierarchy
        """
        pass

    async def error(self, message: str, exc_info: bool = False, **kwargs) -> None:
        """
        Log an error message.

        @docs:use_cases
        - **Exception handling** when errors occur in application code
        - **System failures** that need immediate attention and investigation
        - **Audit trails** for compliance and security requirements

        @docs:examples
        ```python
        try:
            result = await some_operation()
        except Exception as e:
            await logger.error(
                "Operation failed",
                exc_info=True,
                operation="some_operation",
            )
        ```

        @docs:notes
        - Set exc_info=True to include full exception traceback
        - Error logs are typically sent to error monitoring systems
        - See [Error Handling](../concepts/error-handling.md) for best practices
        """
        pass

    async def close(self) -> None:
        """
        Close the logger and cleanup resources.

        @docs:use_cases
        - **Application shutdown** to ensure all logs are flushed
        - **Resource cleanup** to prevent memory leaks and file handle issues
        - **Graceful termination** in containerized environments

        @docs:examples
        ```python
        import asyncio
        from fapilog import get_logger

        logger = get_logger()
        asyncio.run(logger.stop_and_drain())
        ```

        @docs:notes
        - **Always call close()** when done with the logger
        - This ensures all buffered logs are written and resources freed
        - Logger becomes unusable after calling close()
        """
        pass


async def redact_sensitive_data(
    data: Dict[str, Any], patterns: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Redact sensitive information from log data.

    Applies configured redaction patterns to remove or mask sensitive
    data like passwords, API keys, and personal information.

    @docs:use_cases
    - **Compliance requirements** need **automatic data masking** for PII
    - **Security teams** require **configurable redaction patterns** for different data types
    - **Audit logging** benefits from **consistent data handling** across all log entries
    - **Multi-tenant systems** need **tenant-specific redaction rules**

    @docs:examples
    ```python
    from fapilog import get_logger

    logger = get_logger()
    logger.info(
        "User credentials",
        username="john_doe",
        password="secret123",  # masked by default regex redactor
        api_key="sk-1234567890abcdef",
    )
    ```

    @docs:notes
    - Redaction is **applied before logging** - original data is never stored
    - Patterns support **regex** and **glob** matching for flexible configuration
    - **Default patterns** cover common sensitive data types
    - See [Data Redaction](../concepts/data-redaction.md) for pattern configuration
    """
    pass
