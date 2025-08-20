from __future__ import annotations

import asyncio
import gzip
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ...core import diagnostics
from ...core.serialization import (
    SerializedView,
    convert_json_bytes_to_jsonl,
    serialize_envelope,
    serialize_mapping_to_json_bytes,
)


@dataclass
class RotatingFileSinkConfig:
    """Configuration for `RotatingFileSink`.

    Attributes:
        directory: Target directory for log files. Created if missing.
        filename_prefix: Prefix for created files.
        mode: 'json' for JSONL output,
            'text' for deterministic key=value lines.
        max_bytes: Rotate when current file size plus next record would
            exceed this.
        interval_seconds: Optional time-based rotation period.
            If set, rotate at/after next deadline boundary.
        max_files: Optional retention cap on number of rotated files.
            The active file is not counted.
        max_total_bytes: Optional retention cap on cumulative bytes for
            rotated files. The active file is not counted.
        compress_rotated: If True, compress closed (rotated) files to .gz.
    """

    directory: Path
    filename_prefix: str = "fapilog"
    mode: str = "json"  # "json" or "text"
    max_bytes: int = 10 * 1024 * 1024
    interval_seconds: int | None = None
    max_files: int | None = None
    max_total_bytes: int | None = None
    compress_rotated: bool = False


class RotatingFileSink:
    """Async rotating file sink with size/time rotation and retention.

    - JSON mode outputs JSONL using zero-copy serialization helpers
    - Text mode outputs deterministic key=value pairs in sorted-key order
    - Size-based rotation occurs before a write that would breach max_bytes
    - Optional interval rotation occurs at boundary deadlines
    - Retention enforced by `max_files` and/or `max_total_bytes`
    - On filename timestamp collision, a numeric suffix `-<index>` is
      appended
    - Cross-platform paths via `pathlib.Path`
    - All filesystem work happens in threads to avoid event loop stalls
    - Never raises upstream; errors are contained
    """

    _lock: asyncio.Lock

    def __init__(self, config: RotatingFileSinkConfig) -> None:
        self._cfg = config
        self._lock = asyncio.Lock()
        # Internal state
        self._active_path: Path | None = None
        from typing import BinaryIO

        self._active_file: BinaryIO | None = None
        self._active_size: int = 0
        self._next_rotation_deadline: float | None = None

    async def start(self) -> None:
        try:
            async with self._lock:
                self._cfg.directory = Path(self._cfg.directory)
                await asyncio.to_thread(
                    self._cfg.directory.mkdir, parents=True, exist_ok=True
                )
                await self._open_new_file()
        except Exception:
            # Contain initialization errors
            return None

    async def stop(self) -> None:
        try:
            async with self._lock:
                if self._active_file is not None:
                    file_obj = self._active_file
                    self._active_file = None
                    await asyncio.to_thread(file_obj.flush)
                    await asyncio.to_thread(file_obj.close)
                # After closing, enforce retention across all files
                # (including the last active)
                try:
                    await self._enforce_retention()
                except Exception:
                    pass
                self._active_path = None
                self._active_size = 0
                self._next_rotation_deadline = None
        except Exception:
            return None

    async def write(self, entry: dict[str, Any]) -> None:
        try:
            # Serialize first (outside lock) so we can check size/time
            # quickly within lock
            if self._cfg.mode == "json":
                try:
                    view: SerializedView = serialize_envelope(entry)
                except Exception as e:
                    strict = False
                    try:
                        from ...core import settings as _settings

                        strict = bool(_settings.Settings().core.strict_envelope_mode)
                    except Exception:
                        strict = False
                    diagnostics.warn(
                        "sink",
                        "envelope serialization error",
                        mode="strict" if strict else "best-effort",
                        reason=type(e).__name__,
                        detail=str(e),
                    )
                    if strict:
                        return None
                    view = serialize_mapping_to_json_bytes(entry)
                segments = convert_json_bytes_to_jsonl(view)
                payload_segments: tuple[memoryview, ...] = tuple(
                    segments.iter_memoryviews()
                )
                payload_size = segments.total_length
            else:
                # Deterministic text line: key=value with keys sorted,
                # separated by spaces
                try:
                    items = sorted(entry.items(), key=lambda kv: kv[0])
                except Exception:
                    # Fallback: best-effort string conversion
                    # if non-mapping-ish
                    items = [("message", str(entry))]
                line = " ".join(f"{k}={self._stringify(v)}" for k, v in items) + "\n"
                data = line.encode("utf-8", errors="replace")
                payload_segments = (memoryview(data),)
                payload_size = len(data)

            async with self._lock:
                # Ensure active file exists
                if self._active_file is None or self._active_path is None:
                    await self._open_new_file()

                # Check rotation by time
                now = time.time()
                if (
                    self._next_rotation_deadline is not None
                    and now >= self._next_rotation_deadline
                ):
                    await self._rotate_active_file()

                # Check rotation by size (before write)
                if (
                    self._cfg.max_bytes > 0
                    and (self._active_size + payload_size) > self._cfg.max_bytes
                ):
                    await self._rotate_active_file()

                # Write payload segments
                if self._active_file is not None:
                    file_obj = self._active_file

                    def _write_segments() -> None:
                        # Prefer vectored write via os.writev when available
                        try:
                            if hasattr(os, "writev"):
                                os.writev(
                                    file_obj.fileno(),
                                    list(payload_segments),
                                )
                            else:
                                file_obj.writelines(payload_segments)
                        except Exception:
                            # Fallback to simple loop write on any error
                            try:
                                for seg in payload_segments:
                                    file_obj.write(seg)
                            except Exception:
                                pass
                        finally:
                            try:
                                file_obj.flush()
                            except Exception:
                                pass

                    await asyncio.to_thread(_write_segments)
                    self._active_size += payload_size
        except Exception:
            # Contain sink errors
            return None

    async def write_serialized(self, view: SerializedView) -> None:
        try:
            if self._cfg.mode != "json":
                # Only JSON mode supports serialized fast path;
                # ignore gracefully
                return None
            segments = convert_json_bytes_to_jsonl(view)
            payload_segments: tuple[memoryview, ...] = tuple(
                segments.iter_memoryviews()
            )
            payload_size = segments.total_length

            async with self._lock:
                # Ensure active file exists
                if self._active_file is None or self._active_path is None:
                    await self._open_new_file()

                # Check rotation by time
                now = time.time()
                if (
                    self._next_rotation_deadline is not None
                    and now >= self._next_rotation_deadline
                ):
                    await self._rotate_active_file()

                # Check rotation by size (before write)
                if (
                    self._cfg.max_bytes > 0
                    and (self._active_size + payload_size) > self._cfg.max_bytes
                ):
                    await self._rotate_active_file()

                # Write payload segments
                if self._active_file is not None:
                    file_obj = self._active_file

                    def _write_segments() -> None:
                        # Prefer vectored write via os.writev when available
                        try:
                            if hasattr(os, "writev"):
                                os.writev(
                                    file_obj.fileno(),
                                    list(payload_segments),
                                )
                            else:
                                file_obj.writelines(payload_segments)
                        except Exception:
                            try:
                                for seg in payload_segments:
                                    file_obj.write(seg)
                            except Exception:
                                pass
                        finally:
                            try:
                                file_obj.flush()
                            except Exception:
                                pass

                    await asyncio.to_thread(_write_segments)
                    self._active_size += payload_size
        except Exception:
            return None

    # Internal helpers
    async def _open_new_file(self) -> None:
        """Open a new active file with a timestamped name and set deadlines."""
        # Compute next rotation deadline
        if self._cfg.interval_seconds and self._cfg.interval_seconds > 0:
            now = time.time()
            interval = float(self._cfg.interval_seconds)
            # Align to next boundary from current time
            next_boundary = now - (now % interval) + interval
            self._next_rotation_deadline = next_boundary
        else:
            self._next_rotation_deadline = None

        # Build filename
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        base_name = f"{self._cfg.filename_prefix}-{ts}"
        ext = ".jsonl" if self._cfg.mode == "json" else ".log"

        # Resolve collisions by appending -<index>
        path = self._cfg.directory / f"{base_name}{ext}"
        index = 1
        while True:
            exists = await asyncio.to_thread(path.exists)
            if not exists:
                break
            path = self._cfg.directory / f"{base_name}-{index}{ext}"
            index += 1

        # Open binary append
        from typing import BinaryIO

        def _open() -> BinaryIO:
            return open(path, "ab", buffering=0)

        file_obj = await asyncio.to_thread(_open)
        self._active_file = file_obj
        self._active_path = path
        # Determine current size (should be 0 for new file)
        try:
            stat_result = await asyncio.to_thread(path.stat)
            self._active_size = int(stat_result.st_size)
        except Exception:
            self._active_size = 0

    async def _rotate_active_file(self) -> None:
        """Close the current file, optionally compress it, enforce
        retention, and open a new one.
        """
        if self._active_file is None or self._active_path is None:
            await self._open_new_file()
            return

        # Close current file
        file_obj = self._active_file
        path = self._active_path
        self._active_file = None
        await asyncio.to_thread(file_obj.flush)
        await asyncio.to_thread(file_obj.close)

        # Optionally compress the rotated file
        if self._cfg.compress_rotated:
            await self._compress_file(path)

        # Enforce retention on rotated set
        await self._enforce_retention()

        # Open a fresh file
        await self._open_new_file()

    async def _compress_file(self, path: Path) -> None:
        try:
            gz_path = path.with_suffix(path.suffix + ".gz")

            def _compress() -> None:
                with open(path, "rb") as src, gzip.open(
                    gz_path, "wb", compresslevel=5
                ) as dst:
                    while True:
                        chunk = src.read(1024 * 1024)
                        if not chunk:
                            break
                        dst.write(chunk)

            await asyncio.to_thread(_compress)
            # Remove original after successful compression
            await asyncio.to_thread(path.unlink)
        except Exception:
            # Best effort: keep original if compression fails
            return None

    async def _enforce_retention(self) -> None:
        try:
            # Gather rotated files that match prefix and extension
            # (including .gz)
            candidates: list[Path] = await asyncio.to_thread(self._list_rotated_files)

            # Enforce max_files
            if self._cfg.max_files is not None and self._cfg.max_files >= 0:
                # Sort by modified time ascending (oldest first)
                candidates.sort(key=lambda p: p.stat().st_mtime)
                while len(candidates) > self._cfg.max_files:
                    victim = candidates.pop(0)
                    try:
                        await asyncio.to_thread(victim.unlink)
                    except Exception:
                        pass

            # Enforce max_total_bytes
            if self._cfg.max_total_bytes is not None and self._cfg.max_total_bytes >= 0:
                # Recompute sizes and delete oldest until within budget
                def _sizes(
                    paths: Iterable[Path],
                ) -> tuple[list[tuple[Path, int]], int]:
                    sized: list[tuple[Path, int]] = []
                    total = 0
                    for p in paths:
                        try:
                            sz = p.stat().st_size
                        except Exception:
                            sz = 0
                        sized.append((p, sz))
                        total += sz
                    sized.sort(key=lambda t: t[0].stat().st_mtime)
                    return sized, total

                sized, total = await asyncio.to_thread(_sizes, candidates)
                idx = 0
                while total > self._cfg.max_total_bytes and idx < len(sized):
                    victim, vsz = sized[idx]
                    try:
                        await asyncio.to_thread(victim.unlink)
                        total -= vsz
                    except Exception:
                        pass
                    idx += 1
        except Exception:
            # Retention must never break writes
            return None

    def _list_rotated_files(self) -> list[Path]:
        """List files in directory matching prefix and expected extensions.

        Excludes the current active path.
        """
        if not self._cfg.directory.exists():
            return []
        exts = {".jsonl", ".log", ".jsonl.gz", ".log.gz"}
        files: list[Path] = []
        try:
            for p in self._cfg.directory.iterdir():
                if not p.is_file():
                    continue
                name_ok = p.name.startswith(f"{self._cfg.filename_prefix}-")
                ext = p.suffix
                if p.name.endswith(".gz"):
                    # Double suffix handling (.jsonl.gz or .log.gz)
                    ext = "".join(p.suffixes[-2:])
                if name_ok and ext in exts and p != self._active_path:
                    files.append(p)
        except Exception:
            return files
        return files

    def _stringify(self, value: Any) -> str:
        try:
            if isinstance(value, (str, int, float, bool)) or value is None:
                return str(value)
            return str(value)
        except Exception:
            return "<?>"


# Minimal plugin metadata for discovery compatibility (local/entry-point)
PLUGIN_METADATA = {
    "name": "rotating-file-sink",
    "version": "0.1.0",
    "plugin_type": "sink",
    "entry_point": __name__,
    "description": ("Async rotating file sink with size/time rotation and retention"),
    "author": "Fapilog Core",
    "api_version": "1.0",
}

# Mark as referenced for static analyzers (vulture)
_VULTURE_USED: tuple[object, ...] = (
    RotatingFileSink,
    RotatingFileSink.write,  # vulture: used
    RotatingFileSink.write_serialized,  # vulture: used
)
