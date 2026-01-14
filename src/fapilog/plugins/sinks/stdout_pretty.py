from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from typing import Any, Mapping

from ...core.errors import SinkWriteError

COLORS = {
    "DEBUG": "\033[90m",
    "INFO": "\033[34m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "CRITICAL": "\033[1;31m",
    "RESET": "\033[0m",
}
LEVEL_PADDING = 8


class StdoutPrettySink:
    """Async-friendly stdout sink with human-readable console output."""

    name = "stdout_pretty"
    _lock: asyncio.Lock

    def __init__(self, *, colors: bool = True) -> None:
        self._lock = asyncio.Lock()
        self._colors_enabled = bool(colors)
        self._use_colors = self._colors_enabled and self._is_tty()
        self._last_ts_value: Any | None = None
        self._last_ts_text: str | None = None
        self._level_cache: dict[str, str] = {}

    async def start(self) -> None:  # lifecycle placeholder
        return None

    async def stop(self) -> None:  # lifecycle placeholder
        return None

    async def write(self, entry: dict[str, Any]) -> None:
        try:
            formatted = self._format_pretty(entry)
            async with self._lock:

                def _write_line() -> None:
                    sys.stdout.write(formatted + "\n")
                    sys.stdout.flush()

                await asyncio.to_thread(_write_line)
        except Exception as e:
            raise SinkWriteError(
                f"Failed to write to {self.name}",
                sink_name=self.name,
                cause=e,
            ) from e

    async def health_check(self) -> bool:
        try:
            return bool(sys.stdout and sys.stdout.write)
        except Exception:
            return False

    def _is_tty(self) -> bool:
        try:
            isatty = getattr(sys.stdout, "isatty", None)
            return bool(isatty and isatty())
        except Exception:
            return False

    def _format_pretty(self, entry: dict[str, Any]) -> str:
        timestamp = self._format_timestamp(entry.get("timestamp"))
        level = self._format_level(str(entry.get("level", "INFO")))
        message = str(entry.get("message", ""))
        exception_block = self._format_exception(entry)
        context = "" if exception_block else self._format_context(entry)

        base = f"{timestamp} | {level} | {message}"
        if context:
            base = f"{base} {context}"
        if exception_block:
            base = f"{base}\n{exception_block}"
        return base

    def _format_timestamp(self, value: Any) -> str:
        if self._last_ts_value is not None:
            try:
                if value == self._last_ts_value and self._last_ts_text is not None:
                    return self._last_ts_text
            except Exception:
                pass
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(float(value))
        elif isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except Exception:
                return value[:19] if len(value) >= 19 else value
        else:
            return "" if value is None else str(value)

        if dt.tzinfo is not None:
            dt = dt.astimezone()
        text = dt.strftime("%Y-%m-%d %H:%M:%S")
        self._last_ts_value = value
        self._last_ts_text = text
        return text

    def _format_level(self, level: str) -> str:
        cached = self._level_cache.get(level)
        if cached is not None:
            return cached
        padded = level.ljust(LEVEL_PADDING)
        if self._use_colors and level in COLORS:
            formatted = f"{COLORS[level]}{padded}{COLORS['RESET']}"
        else:
            formatted = padded
        self._level_cache[level] = formatted
        return formatted

    def _format_context(self, entry: dict[str, Any]) -> str:
        context = self._collect_context(entry)
        parts: list[str] = []
        for key, value in context.items():
            self._append_context_pairs(str(key), value, parts)
        return " ".join(parts)

    def _collect_context(self, entry: dict[str, Any]) -> dict[str, Any]:
        context: dict[str, Any] = {}
        base = entry.get("context")
        if isinstance(base, Mapping):
            context.update(base)
        meta = entry.get("metadata")
        if isinstance(meta, Mapping):
            context.update(meta)
        for key, value in entry.items():
            if key in {"timestamp", "level", "message", "context", "metadata"}:
                continue
            context.setdefault(key, value)
        return context

    def _append_context_pairs(self, key: str, value: Any, out: list[str]) -> None:
        if key.startswith("error."):
            return
        if isinstance(value, Mapping):
            for nested_key, nested_value in value.items():
                self._append_context_pairs(f"{key}.{nested_key}", nested_value, out)
            return
        out.append(f"{key}={self._format_value(value)}")

    def _format_value(self, value: Any) -> str:
        if isinstance(value, str):
            if " " in value:
                return f"'{value}'"
            return value
        return str(value)

    def _format_exception(self, entry: dict[str, Any]) -> str:
        meta = entry.get("metadata")
        error_type = None
        error_message = None
        frames = None
        if isinstance(meta, Mapping):
            error_type = meta.get("error.type")
            error_message = meta.get("error.message")
            frames = meta.get("error.frames")

        if isinstance(frames, list) and frames:
            lines = ["Traceback (most recent call last):"]
            for frame in frames:
                if not isinstance(frame, Mapping):
                    continue
                filename = frame.get("file") or "<unknown>"
                lineno = frame.get("line") or "?"
                func = frame.get("function") or "<unknown>"
                lines.append(f'  File "{filename}", line {lineno}, in {func}')
                code = frame.get("code")
                if code:
                    lines.append(f"    {code}")
            if error_type:
                if error_message:
                    lines.append(f"{error_type}: {error_message}")
                else:
                    lines.append(str(error_type))
            text = "\n".join(lines)
            context = self._format_context(entry)
            if context:
                return f"{text}\nContext: {context}"
            return text

        stack = None
        exc = entry.get("exception")
        if isinstance(exc, Mapping):
            stack = exc.get("traceback") or exc.get("stack")
        if not stack and isinstance(meta, Mapping):
            stack = meta.get("error.stack")
        if not stack:
            stack = entry.get("error.stack")
        if not stack:
            return ""
        text = str(stack).rstrip()
        context = self._format_context(entry)
        if context:
            return f"{text}\nContext: {context}"
        return text


PLUGIN_METADATA = {
    "name": "stdout_pretty",
    "version": "1.0.0",
    "plugin_type": "sink",
    "entry_point": "fapilog.plugins.sinks.stdout_pretty:StdoutPrettySink",
    "description": "Async stdout pretty console sink",
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "0.3.0"},
    "api_version": "1.0",
}
