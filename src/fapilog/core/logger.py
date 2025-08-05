"""
Async-first logger for fapilog v3.

This module provides the AsyncLogger class that implements async-first
logging with zero-copy operations and parallel processing.
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from .events import EventCategory, LogEvent
from .settings import UniversalSettings


class AsyncLogger:
    """Async-first logger with zero-copy operations and parallel processing."""

    def __init__(self, settings: UniversalSettings):
        """Initialize async logger with settings."""
        self.settings = settings
        self._queue: Optional[asyncio.Queue] = None
        self._workers: List[asyncio.Task] = []
        self._running = False

    @classmethod
    async def create(cls, settings: UniversalSettings) -> "AsyncLogger":
        """Create and configure async logger."""
        logger = cls(settings)
        await logger._initialize()
        return logger

    async def _initialize(self) -> None:
        """Initialize the async logger components."""
        if self.settings.async_processing:
            self._queue = asyncio.Queue(maxsize=self.settings.queue_max_size)
            await self._start_workers()
            self._running = True

    async def _start_workers(self) -> None:
        """Start parallel processing workers."""
        for _ in range(self.settings.max_workers):
            worker = asyncio.create_task(self._worker())
            self._workers.append(worker)

    async def _worker(self) -> None:
        """Worker task for parallel event processing."""
        while self._running and self._queue:
            try:
                event = await self._queue.get()
                await self._process_event(event)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log worker errors
                print(f"Worker error: {e}")

    async def _process_event(self, event: LogEvent) -> None:
        """Process a single log event."""
        # Apply zero-copy operations if enabled
        if self.settings.zero_copy_operations:
            await self._process_zero_copy(event)
        else:
            await self._process_standard(event)

    async def _process_zero_copy(self, event: LogEvent) -> None:
        """Process event with zero-copy operations."""
        # Zero-copy serialization and processing
        event_dict = event.to_dict()

        # Parallel sink writing
        if self.settings.parallel_processing:
            await self._write_to_sinks_parallel(event_dict)
        else:
            await self._write_to_sinks_sequential(event_dict)

    async def _process_standard(self, event: LogEvent) -> None:
        """Process event with standard operations."""
        event_dict = event.to_dict()
        await self._write_to_sinks_sequential(event_dict)

    async def _write_to_sinks_parallel(self, event_dict: Dict[str, Any]) -> None:
        """Write to sinks in parallel."""
        tasks = []
        for sink_uri in self.settings.sinks:
            task = asyncio.create_task(self._write_to_sink(sink_uri, event_dict))
            tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _write_to_sinks_sequential(self, event_dict: Dict[str, Any]) -> None:
        """Write to sinks sequentially."""
        for sink_uri in self.settings.sinks:
            await self._write_to_sink(sink_uri, event_dict)

    async def _write_to_sink(self, sink_uri: str, event_dict: Dict[str, Any]) -> None:
        """Write event to a specific sink."""
        # TODO: Implement sink writing logic
        print(f"Writing to sink {sink_uri}: {event_dict}")

    async def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        await self._log("INFO", message, **kwargs)

    async def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        await self._log("DEBUG", message, **kwargs)

    async def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        await self._log("WARNING", message, **kwargs)

    async def error(self, message: str, **kwargs: Any) -> None:
        """Log error message."""
        await self._log("ERROR", message, **kwargs)

    async def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message."""
        await self._log("CRITICAL", message, **kwargs)

    async def _log(self, level: str, message: str, **kwargs: Any) -> None:
        """Internal logging method."""
        # Create log event
        event = LogEvent(
            message=message,
            level=level,
            timestamp=datetime.now(),
            source=kwargs.get("source", ""),
            category=kwargs.get("category", EventCategory.SYSTEM),
            severity=kwargs.get("severity", 3),
            tags=kwargs.get("tags", {}),
            context=kwargs.get("context", {}),
            metrics=kwargs.get("metrics", {}),
            correlation_id=kwargs.get("correlation_id", ""),
        )

        # Add custom context
        for key, value in kwargs.items():
            if key not in [
                "source",
                "category",
                "severity",
                "tags",
                "context",
                "metrics",
                "correlation_id",
            ]:
                event.add_context(key, value)

        # Enqueue event for async processing
        if self._queue and self._running:
            await self._queue.put(event)
        else:
            # Fallback to synchronous processing
            await self._process_event(event)

    async def shutdown(self) -> None:
        """Shutdown the async logger gracefully."""
        self._running = False

        # Cancel all workers
        for worker in self._workers:
            worker.cancel()

        # Wait for workers to finish
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)

        # Process remaining events in queue
        if self._queue:
            while not self._queue.empty():
                event = await self._queue.get()
                await self._process_event(event)

    async def __aenter__(self) -> "AsyncLogger":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.shutdown()
