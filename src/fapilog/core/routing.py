from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Iterable

from ..plugins.utils import get_plugin_name, normalize_plugin_name
from . import diagnostics
from .circuit_breaker import SinkCircuitBreaker


@dataclass
class _SinkEntry:
    name: str
    sink: Any
    write: Any
    write_serialized: Any
    breaker: SinkCircuitBreaker | None


def _make_sink_entry(
    sink: Any,
    circuit_config: Any | None,
) -> _SinkEntry:
    async def _write(entry: dict[str, Any]) -> bool | None:
        if hasattr(sink, "start") and not getattr(sink, "_started", False):
            try:
                await sink.start()
                sink._started = True  # noqa: SLF001
            except Exception:
                try:
                    diagnostics.warn(
                        "sink",
                        "sink start failed",
                        sink_type=type(sink).__name__,
                    )
                except Exception:
                    pass
        result: bool | None = await sink.write(entry)
        return result

    async def _write_serialized(view: Any) -> bool | None:
        try:
            result: bool | None = await sink.write_serialized(view)
            return result
        except AttributeError:
            return None

    breaker = None
    if circuit_config is not None and getattr(circuit_config, "enabled", False):
        breaker = SinkCircuitBreaker(
            getattr(sink, "name", type(sink).__name__),
            circuit_config,
        )

    return _SinkEntry(
        name=normalize_plugin_name(get_plugin_name(sink)),
        sink=sink,
        write=_write,
        write_serialized=_write_serialized,
        breaker=breaker,
    )


def _normalize_level(level: str) -> str:
    return level.upper()


class RoutingSinkWriter:
    """Route events to sinks based on log level."""

    def __init__(
        self,
        sinks: Iterable[Any],
        rules: list[tuple[set[str], list[str]]],
        fallback_sink_names: list[str],
        *,
        overlap: bool = True,
        parallel: bool = False,
        circuit_config: Any | None = None,
    ) -> None:
        self._parallel = parallel
        self._overlap = overlap

        entries = [_make_sink_entry(s, circuit_config) for s in sinks]
        self._sink_entries: dict[str, _SinkEntry] = {e.name: e for e in entries}

        self._level_to_entries: dict[str, list[_SinkEntry]] = {}
        self._fallback_entries: list[_SinkEntry] = []
        used_sink_names: set[str] = set()

        for level_set, sink_names in rules:
            resolved = [
                self._sink_entries[normalize_plugin_name(name)]
                for name in sink_names
                if normalize_plugin_name(name) in self._sink_entries
            ]
            used_sink_names.update(
                normalize_plugin_name(name)
                for name in sink_names
                if normalize_plugin_name(name) in self._sink_entries
            )
            wildcard = False
            for level in level_set:
                norm_level = _normalize_level(level)
                if norm_level == "*":
                    wildcard = True
                    continue
                if self._overlap:
                    self._level_to_entries.setdefault(norm_level, []).extend(resolved)
                else:
                    self._level_to_entries.setdefault(norm_level, resolved)
            if wildcard and resolved:
                self._fallback_entries.extend(resolved)

        self._fallback_entries.extend(
            [
                self._sink_entries[name]
                for name in map(normalize_plugin_name, fallback_sink_names)
                if name in self._sink_entries
            ]
        )
        used_sink_names.update(entry.name for entry in self._fallback_entries)

        unmatched = set(self._sink_entries) - used_sink_names
        if unmatched:
            try:
                diagnostics.warn(
                    "sink-routing",
                    "sinks configured but not targeted by routing rules",
                    sinks=sorted(unmatched),
                    _rate_limit_key="routing-unused",
                )
            except Exception:
                pass

    def get_sinks_for_level(self, level: str) -> list[_SinkEntry]:
        norm = _normalize_level(level)
        if norm in self._level_to_entries:
            return self._level_to_entries[norm]
        return self._fallback_entries

    async def write(self, entry: dict[str, Any]) -> None:
        level = entry.get("level", "INFO")
        targets = self.get_sinks_for_level(str(level))
        if not targets:
            return

        if self._parallel and len(targets) > 1:
            await asyncio.gather(
                *[self._write_one(target, entry) for target in targets],
                return_exceptions=True,
            )
        else:
            for target in targets:
                await self._write_one(target, entry)

    async def write_serialized(self, view: Any, *, level: str | None = None) -> None:
        lvl = level or getattr(view, "level", None) or "INFO"
        targets = self.get_sinks_for_level(str(lvl))
        if not targets:
            return

        if self._parallel and len(targets) > 1:
            await asyncio.gather(
                *[self._write_one(target, view, serialized=True) for target in targets],
                return_exceptions=True,
            )
        else:
            for target in targets:
                await self._write_one(target, view, serialized=True)

    async def _write_one(
        self,
        target: _SinkEntry,
        payload: Any,
        *,
        serialized: bool = False,
    ) -> None:
        breaker = target.breaker
        if breaker and not breaker.should_allow():
            return

        try:
            if serialized:
                result = await target.write_serialized(payload)
            else:
                result = await target.write(payload)
            # False return signals failure (Story 4.41)
            if result is False:
                if breaker:
                    breaker.record_failure()
                try:
                    from ..plugins.sinks.fallback import handle_sink_write_failure

                    await handle_sink_write_failure(
                        payload,
                        sink=target.sink,
                        error=RuntimeError("Sink returned False"),
                        serialized=serialized,
                    )
                except Exception:
                    pass
            elif breaker:
                breaker.record_success()
        except Exception as exc:
            if breaker:
                breaker.record_failure()
            try:
                from ..plugins.sinks.fallback import handle_sink_write_failure

                await handle_sink_write_failure(
                    payload,
                    sink=target.sink,
                    error=exc,
                    serialized=serialized,
                )
            except Exception:
                pass

    def update_rules(
        self, rules: list[tuple[set[str], list[str]]], fallback_sink_names: list[str]
    ) -> None:
        self._level_to_entries.clear()
        self._fallback_entries = [
            self._sink_entries[name]
            for name in map(normalize_plugin_name, fallback_sink_names)
            if name in self._sink_entries
        ]
        for level_set, sink_names in rules:
            resolved = [
                self._sink_entries[normalize_plugin_name(name)]
                for name in sink_names
                if normalize_plugin_name(name) in self._sink_entries
            ]
            for level in level_set:
                norm_level = _normalize_level(level)
                if norm_level == "*":
                    self._fallback_entries.extend(resolved)
                    continue
                if self._overlap:
                    self._level_to_entries.setdefault(norm_level, []).extend(resolved)
                else:
                    self._level_to_entries.setdefault(norm_level, resolved)


def build_routing_writer(
    sinks: list[Any],
    routing_config: Any,
    *,
    parallel: bool = False,
    circuit_config: Any | None = None,
) -> tuple[Any, Any]:
    """Return (write, write_serialized) callables honoring routing config."""

    rules = [
        ({lvl.upper() for lvl in rule.levels}, list(rule.sinks))
        for rule in getattr(routing_config, "rules", [])
    ]
    fallback = getattr(routing_config, "fallback_sinks", []) or []
    if isinstance(fallback, str):
        fallback = [v for v in (item.strip() for item in fallback.split(",")) if v]

    writer = RoutingSinkWriter(
        sinks,
        rules,
        fallback,
        overlap=getattr(routing_config, "overlap", True),
        parallel=parallel,
        circuit_config=circuit_config,
    )

    async def _write(entry: dict[str, Any]) -> None:
        await writer.write(entry)

    async def _write_serialized(view: Any) -> None:
        level = getattr(view, "level", None)
        await writer.write_serialized(view, level=level)

    return _write, _write_serialized
