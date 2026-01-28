from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ...core import diagnostics
from .. import loader
from ..utils import normalize_plugin_name

if TYPE_CHECKING:  # pragma: no cover
    from ...metrics.metrics import MetricsCollector


@dataclass
class RoutingSinkConfig:
    """Configuration for the routing sink."""

    routes: dict[str, list[str]] = field(default_factory=dict)
    sink_configs: dict[str, dict[str, Any]] = field(default_factory=dict)
    parallel: bool = False
    overlap: bool = True


class RoutingSink:
    """Sink that routes events to other sinks based on log level."""

    name = "routing"

    def __init__(
        self,
        config: RoutingSinkConfig | None = None,
        *,
        metrics: MetricsCollector | None = None,
        **kwargs: Any,
    ) -> None:
        self._config = config or RoutingSinkConfig(**kwargs)
        self._metrics = metrics
        self._sinks: dict[str, Any] = {}
        self._level_to_sinks: dict[str, list[Any]] = {}
        self._fallback: list[Any] = []

    async def start(self) -> None:
        all_sink_names: set[str] = set()
        for names in self._config.routes.values():
            all_sink_names.update(names)
        for sink_key in self._config.sink_configs.keys():
            all_sink_names.add(sink_key)

        for sink_name in all_sink_names:
            try:
                sink_cfg = self._config.sink_configs.get(sink_name, {})
                sink = loader.load_plugin("fapilog.sinks", sink_name, sink_cfg)
                if hasattr(sink, "start"):
                    await sink.start()
                self._sinks[normalize_plugin_name(sink_name)] = sink
            except Exception as exc:
                diagnostics.warn(
                    "routing-sink",
                    "failed to load child sink",
                    sink=sink_name,
                    error=str(exc),
                    _rate_limit_key="routing-load",
                )

        for level, names in self._config.routes.items():
            target_instances = [
                self._sinks[normalize_plugin_name(name)]
                for name in names
                if normalize_plugin_name(name) in self._sinks
            ]
            if level.strip() == "*":
                self._fallback = target_instances
                continue
            normalized_level = level.upper()
            if self._config.overlap:
                self._level_to_sinks.setdefault(normalized_level, []).extend(
                    target_instances
                )
            else:
                self._level_to_sinks.setdefault(normalized_level, target_instances)

    async def stop(self) -> None:
        for sink in self._sinks.values():
            try:
                if hasattr(sink, "stop"):
                    await sink.stop()
            except Exception:
                pass

    async def write(self, entry: dict[str, Any]) -> None:
        level = str(entry.get("level", "INFO")).upper()
        targets = self._level_to_sinks.get(level, self._fallback)
        if not targets:
            return

        if self._config.parallel and len(targets) > 1:
            await asyncio.gather(
                *[self._write_one(s, entry) for s in targets],
                return_exceptions=True,
            )
        else:
            for sink in targets:
                await self._write_one(sink, entry)

    async def _write_one(self, sink: Any, entry: dict[str, Any]) -> None:
        sink_name = getattr(sink, "name", type(sink).__name__)
        try:
            await sink.write(entry)
        except Exception as exc:
            diagnostics.warn(
                "routing-sink",
                "child sink write failed",
                sink=sink_name,
                error=type(exc).__name__,
                _rate_limit_key=f"routing-{sink_name}",
            )
            if self._metrics is not None:
                await self._metrics.record_sink_error(sink=sink_name)

    async def health_check(self) -> bool:
        if not self._sinks:
            return False
        for sink in self._sinks.values():
            if hasattr(sink, "health_check"):
                try:
                    if not await sink.health_check():
                        return False
                except Exception:
                    return False
        return True


PLUGIN_METADATA = {
    "name": "routing",
    "version": "1.0.0",
    "plugin_type": "sink",
    "entry_point": "fapilog.plugins.sinks.routing:RoutingSink",
    "description": "Routes log events to different sinks based on log level.",
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "0.3.0"},
    "api_version": "1.0",
    "dependencies": [],
}


__all__ = ["RoutingSink", "RoutingSinkConfig", "PLUGIN_METADATA"]
