"""
Memory-mapped persistence engine for zero-copy friendly file I/O.

This sink provides an async-first API while internally offloading blocking
file operations (open, truncate, mmap) to a thread using asyncio.to_thread.

Design goals:
- Zero-copy friendly: accept memoryview/bytes from serializers without
  intermediate string conversions; callers can pass SerializedView.view.
- Async-first: public methods are async; blocking work is delegated to threads.
- Safe resizing: grows the underlying file in chunked increments when needed.
- Isolation: no global state; intended to be used via instance per file.
"""

from __future__ import annotations

import asyncio
import mmap
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Union

from ...core.errors import (
    ErrorCategory,
    ErrorSeverity,
    FapilogError,
    create_error_context,
)

BytesLike = Union[bytes, bytearray, memoryview]


@dataclass
class PersistenceStats:
    """Simple stats snapshot for observability/testing."""

    file_size_bytes: int
    write_offset: int
    total_bytes_written: int


class MemoryMappedPersistence:
    """Async memory-mapped persistence for append-only writes.

    Notes:
    - Writes are append-only and not transactional; callers should add
      framing (e.g., newline) as needed.
    - The file is grown in chunks to minimize remapping overhead.
    - Thread-safety: guarded by an asyncio.Lock for concurrent appends.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        initial_size_bytes: int = 1024 * 1024,
        growth_chunk_bytes: int = 1024 * 1024,
        max_size_bytes: int | None = None,
        flush_on_close: bool = True,
        periodic_flush_bytes: int | None = None,
    ) -> None:
        if initial_size_bytes <= 0 or growth_chunk_bytes <= 0:
            raise ValueError("initial_size_bytes and growth_chunk_bytes must be > 0")
        self._path = Path(path)
        self._initial_size = int(initial_size_bytes)
        self._growth_chunk = int(growth_chunk_bytes)
        self._max_size = int(max_size_bytes) if max_size_bytes is not None else None

        self._fd: int | None = None
        self._mmap: mmap.mmap | None = None
        self._size: int = 0
        self._offset: int = 0
        self._lock = asyncio.Lock()
        self._closed: bool = True
        self._flush_on_close = bool(flush_on_close)
        self._periodic_flush_bytes = (
            int(periodic_flush_bytes) if (periodic_flush_bytes) else None
        )

    async def __aenter__(self) -> MemoryMappedPersistence:
        await self.open()
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: object | None,
    ) -> None:
        await self.close()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def is_open(self) -> bool:
        return not self._closed

    async def open(self) -> None:
        """Create directories, open file descriptor, and map memory.

        Idempotent: safe to call if already open.
        """
        if self.is_open:
            return

        try:
            # Ensure parent directory exists (potentially blocking)
            await asyncio.to_thread(
                self._path.parent.mkdir,
                parents=True,
                exist_ok=True,
            )

            # Open or create the file and ensure initial size
            def _open_and_prepare() -> tuple[int, int]:
                flags = os.O_RDWR | os.O_CREAT
                fd = os.open(self._path, flags, 0o644)
                try:
                    current_size = os.path.getsize(self._path)
                    target_size = max(current_size, self._initial_size)
                    if current_size < target_size:
                        os.ftruncate(fd, target_size)
                    return fd, target_size
                except Exception:
                    os.close(fd)
                    raise

            self._fd, self._size = await asyncio.to_thread(_open_and_prepare)

            # Create the mmap
            def _map(fd: int, size: int) -> mmap.mmap:
                return mmap.mmap(fd, size, access=mmap.ACCESS_WRITE)

            assert self._fd is not None
            fd_local = self._fd
            self._mmap = await asyncio.to_thread(_map, fd_local, self._size)
            self._offset = 0
            self._closed = False
        except Exception as e:  # pragma: no cover - rare path aggregation
            context = create_error_context(
                ErrorCategory.IO,
                ErrorSeverity.HIGH,
            )
            raise FapilogError(
                "Failed to open memory-mapped file",
                error_context=context,
                cause=e,
            ) from e

    async def close(self) -> None:
        """Flush and close mmap and file descriptor."""
        if self._closed:
            return
        # Close in thread to avoid blocking loop
        async with self._lock:
            try:
                if self._mmap is not None:
                    if self._flush_on_close:
                        await asyncio.to_thread(self._mmap.flush)
                    await asyncio.to_thread(self._mmap.close)
                if self._fd is not None:
                    # Trim file to actual written length to avoid trailing NULs
                    if 0 <= self._offset <= self._size:
                        fd_local = self._fd
                        await asyncio.to_thread(
                            os.ftruncate,
                            fd_local,
                            self._offset,
                        )
                    await asyncio.to_thread(os.close, self._fd)
            finally:
                self._mmap = None
                self._fd = None
                self._closed = True

    async def _ensure_capacity(self, additional: int) -> None:
        """Grow file/mmap if appending additional bytes exceeds capacity."""
        needed = self._offset + additional
        if needed <= self._size:
            return

        new_size = self._size
        while new_size < needed:
            new_size += self._growth_chunk
        if self._max_size is not None and new_size > self._max_size:
            context = create_error_context(
                ErrorCategory.IO,
                ErrorSeverity.HIGH,
            )
            raise FapilogError(
                "Exceeded maximum persistence file size",
                error_context=context,
            )

        # Remap sequence must be done without other writers
        # Close old map, extend file, and create new map
        assert self._fd is not None

        # Close existing mmap before resizing the file
        if self._mmap is not None:
            await asyncio.to_thread(self._mmap.flush)
            await asyncio.to_thread(self._mmap.close)
            self._mmap = None

        # Resize file
        fd_local = self._fd
        await asyncio.to_thread(os.ftruncate, fd_local, new_size)

        # Create new mmap with updated size
        def _map(fd: int, size: int) -> mmap.mmap:
            return mmap.mmap(fd, size, access=mmap.ACCESS_WRITE)

        self._mmap = await asyncio.to_thread(_map, fd_local, new_size)
        self._size = new_size

    async def append(self, data: BytesLike) -> tuple[int, int]:
        """Append bytes to the mapped file.

        Returns (offset, length) written.
        """
        if self._closed or self._mmap is None:
            await self.open()

        # Normalize to memoryview without copying
        mv = data if isinstance(data, memoryview) else memoryview(data)

        async with self._lock:
            await self._ensure_capacity(len(mv))

            assert self._mmap is not None
            start = self._offset
            end = start + len(mv)

            # Assign directly from memoryview to mmap slice
            def _write() -> None:
                self._mmap[start:end] = mv  # type: ignore[index]

            await asyncio.to_thread(_write)
            # Optional periodic flush hint for durability-sensitive cases
            if (
                self._periodic_flush_bytes is not None
                and self._offset % self._periodic_flush_bytes == 0
                and self._mmap is not None
            ):
                await asyncio.to_thread(self._mmap.flush)
            self._offset = end
            return start, len(mv)

    async def append_line(self, data: BytesLike) -> tuple[int, int]:
        """Append data followed by a newline. Convenience for JSONL."""
        if isinstance(data, memoryview):
            # Combine without copying by two appends
            off1, n1 = await self.append(data)
            _, n2 = await self.append(b"\n")
            return off1, n1 + n2
        else:
            # For bytes/bytearray, still do two appends to avoid allocation
            off1, n1 = await self.append(memoryview(data))
            _, n2 = await self.append(b"\n")
            return off1, n1 + n2

    async def stats(self) -> PersistenceStats:
        """Return a snapshot of current persistence stats."""
        return PersistenceStats(
            file_size_bytes=self._size,
            write_offset=self._offset,
            total_bytes_written=self._offset,
        )
