from __future__ import annotations

import abc
import asyncio
import time
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class CloudSinkConfig:
    """Base configuration shared by cloud sinks."""

    batch_size: int = 100
    batch_timeout_seconds: float = 5.0
    max_retries: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 30.0


class CloudSinkBase(abc.ABC, Generic[T]):
    """Abstract base class providing batching and retry helpers."""

    name: str = "cloud_base"

    def __init__(self, config: CloudSinkConfig) -> None:
        self._config = config
        self._batch: list[T] = []
        self._batch_lock = asyncio.Lock()
        self._flush_task: asyncio.Task[None] | None = None
        self._last_flush = time.monotonic()

    async def start(self) -> None:
        await self._initialize_client()
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def stop(self) -> None:
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self._flush_batch()
        await self._cleanup_client()

    async def write(self, entry: dict) -> None:
        """Transform and enqueue an entry for batching."""
        try:
            transformed = self._transform_entry(entry)
            flush_now = False
            async with self._batch_lock:
                self._batch.append(transformed)
                if len(self._batch) >= self._config.batch_size:
                    flush_now = True
            if flush_now:
                await self._flush_batch()
        except Exception:
            # Contain errors from user transformations
            return None

    async def _flush_loop(self) -> None:
        """Background flush loop controlled by batch_timeout."""
        while True:
            await asyncio.sleep(self._config.batch_timeout_seconds)
            if self._batch:
                await self._flush_batch()

    async def _flush_batch(self) -> None:
        async with self._batch_lock:
            if not self._batch:
                return
            batch = self._batch[:]
            self._batch = []
        await self._send_with_retry(batch)
        self._last_flush = time.monotonic()

    async def _send_with_retry(self, batch: list[T]) -> None:
        delay = self._config.retry_base_delay
        for attempt in range(self._config.max_retries):
            try:
                await self._send_batch(batch)
                return
            except Exception:
                if attempt == self._config.max_retries - 1:
                    return
                await asyncio.sleep(delay)
                delay = min(delay * 2, self._config.retry_max_delay)

    @abc.abstractmethod
    async def _initialize_client(self) -> None:
        """Initialize cloud SDK client(s)."""

    @abc.abstractmethod
    async def _cleanup_client(self) -> None:
        """Clean up cloud SDK client(s)."""

    @abc.abstractmethod
    def _transform_entry(self, entry: dict) -> T:
        """Transform an event into a cloud-specific payload."""

    @abc.abstractmethod
    async def _send_batch(self, batch: list[T]) -> None:
        """Send a batch to the cloud provider."""

    @abc.abstractmethod
    async def health_check(self) -> bool:
        """Check connectivity for readiness probes."""
