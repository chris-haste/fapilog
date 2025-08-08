"""
Configuration hot-reloading utilities.
Provides a polling-based reloader with validation, notification, and rollback.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from .change_detection import ChangeEvent, watch_file_changes
from .errors import ConfigurationError
from .plugin_config import ValidationResult
from .settings import Settings

OnSettingsApplied = Callable[[Settings], Awaitable[None]]
OnReloadError = Callable[[Exception], Awaitable[None]]


class ConfigHotReloader:
    def __init__(
        self,
        *,
        path: str,
        loader: Callable[[], Awaitable[Settings]],
        validator: Callable[[Settings], Awaitable[ValidationResult]] | None = None,
        on_applied: OnSettingsApplied | None = None,
        on_error: OnReloadError | None = None,
        interval_seconds: float = 0.5,
    ) -> None:
        self._path = path
        self._loader = loader
        self._validator = validator
        self._on_applied = on_applied
        self._on_error = on_error
        self._interval_seconds = interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event | None = None
        self._subscribers: list[OnSettingsApplied] = []
        self._last_good: Settings | None = None

    def subscribe(self, callback: OnSettingsApplied) -> None:
        self._subscribers.append(callback)

    async def _notify_applied(self, settings: Settings) -> None:
        if self._on_applied:
            await self._on_applied(settings)
        for cb in self._subscribers:
            await cb(settings)

    async def _notify_error(self, exc: Exception) -> None:
        if self._on_error:
            await self._on_error(exc)

    async def _on_change(self, _: ChangeEvent) -> None:
        try:
            new_settings = await self._loader()
            if self._validator:
                result = await self._validator(new_settings)
                result.raise_if_error(plugin_name="hot-reload")
            # Apply and record
            self._last_good = new_settings
            await self._notify_applied(new_settings)
        except Exception as e:  # noqa: BLE001
            # Rollback is implicit: we keep last_good as active; report error
            await self._notify_error(ConfigurationError("Hot reload failed", cause=e))

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(
            watch_file_changes(
                path=self._path,
                interval_seconds=self._interval_seconds,
                on_change=self._on_change,
                stop_event=self._stop_event,
            )
        )

    async def stop(self) -> None:
        if self._stop_event is None:
            return
        self._stop_event.set()
        if self._task:
            await asyncio.wait([self._task])
        self._task = None
        self._stop_event = None
