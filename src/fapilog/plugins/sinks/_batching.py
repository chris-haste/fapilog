from __future__ import annotations

import asyncio
import time
from typing import Any


class BatchingMixin:
    """Mixin providing batch accumulation with size/timeout triggers."""

    _batch: list[dict[str, Any]]
    _batch_lock: asyncio.Lock
    _batch_first_time: float | None
    _flush_task: asyncio.Task[None] | None
    _batch_size: int
    _batch_timeout_seconds: float

    def _init_batching(self, batch_size: int, batch_timeout_seconds: float) -> None:
        self._batch = []
        self._batch_lock = asyncio.Lock()
        self._batch_first_time: float | None = None
        self._flush_task = None
        self._batch_size = max(1, int(batch_size))
        self._batch_timeout_seconds = float(batch_timeout_seconds)

    async def _start_batching(self) -> None:
        if self._batch_size > 1:
            self._flush_task = asyncio.create_task(self._flush_loop())

    async def _stop_batching(self) -> None:
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None
        await self._flush_batch()

    async def _enqueue_for_batch(self, entry: dict[str, Any]) -> None:
        if self._batch_size <= 1:
            await self._send_batch([entry])
            return

        flush_now = False
        async with self._batch_lock:
            if not self._batch:
                self._batch_first_time = time.monotonic()
            self._batch.append(entry)
            if len(self._batch) >= self._batch_size:
                flush_now = True

        if flush_now:
            await self._flush_batch()

    async def _flush_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._batch_timeout_seconds / 2)
                batch: list[dict[str, Any]] | None = None
                async with self._batch_lock:
                    if not self._batch or self._batch_first_time is None:
                        continue
                    elapsed = time.monotonic() - self._batch_first_time
                    if elapsed >= self._batch_timeout_seconds:
                        batch = self._batch[:]
                        self._batch = []
                        self._batch_first_time = None
                if batch:
                    try:
                        await self._send_batch(batch)
                    except Exception:
                        # Contain errors to keep flush loop alive
                        pass
        except asyncio.CancelledError:
            return

    async def _flush_batch(self) -> None:
        async with self._batch_lock:
            if not self._batch:
                return
            batch = self._batch[:]
            self._batch = []
            self._batch_first_time = None
        await self._send_batch(batch)

    async def _send_batch(
        self, batch: list[dict[str, Any]]
    ) -> None:  # pragma: no cover - abstract
        raise NotImplementedError
