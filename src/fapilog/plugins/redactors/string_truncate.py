"""Per-field string truncation redactor.

Truncates any string value exceeding ``max_string_length`` characters and
appends a ``[truncated]`` marker. Emits a diagnostic for each truncated
field. When disabled (``max_string_length is None``), returns the event
immediately with zero traversal.

Story 10.54: Per-Field String Truncation
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ...core import diagnostics
from ..utils import parse_plugin_config


class StringTruncateConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)

    max_string_length: int | None = Field(
        default=None,
        ge=1,
        description="Maximum character length for string values (None = disabled)",
    )
    max_depth: int = Field(default=16, ge=1, description="Max nested depth to scan")
    max_keys_scanned: int = Field(
        default=1000, ge=1, description="Max keys to scan before stopping"
    )
    on_guardrail_exceeded: Literal["warn", "drop"] = "warn"


class StringTruncateRedactor:
    name = "string_truncate"

    def __init__(
        self,
        *,
        config: StringTruncateConfig | dict | None = None,
        core_max_depth: int | None = None,
        core_max_keys_scanned: int | None = None,
        **kwargs: Any,
    ) -> None:
        cfg = parse_plugin_config(StringTruncateConfig, config, **kwargs)
        self._max_len = cfg.max_string_length
        self._marker = "[truncated]"
        self._on_guardrail_exceeded = cfg.on_guardrail_exceeded

        plugin_depth = int(cfg.max_depth)
        plugin_scanned = int(cfg.max_keys_scanned)

        if core_max_depth is not None:
            self._max_depth = min(plugin_depth, core_max_depth)
        else:
            self._max_depth = plugin_depth

        if core_max_keys_scanned is not None:
            self._max_scanned = min(plugin_scanned, core_max_keys_scanned)
        else:
            self._max_scanned = plugin_scanned

        self.last_redacted_count: int = 0

    async def start(self) -> None:  # pragma: no cover - optional lifecycle
        return None

    async def stop(self) -> None:  # pragma: no cover - optional lifecycle
        return None

    async def redact(self, event: dict) -> dict:
        if self._max_len is None:
            return event

        self.last_redacted_count = 0
        guardrail_hit = False

        def _copy_and_traverse(
            container: Any,
            depth: int,
            path_parts: list[str],
        ) -> Any:
            nonlocal guardrail_hit

            if depth > self._max_depth:
                guardrail_hit = True
                diagnostics.warn(
                    "redactor",
                    "max depth exceeded during string truncation",
                    path=".".join(path_parts),
                )
                return container

            if isinstance(container, dict):
                copy = dict(container)
                for key in list(copy.keys()):
                    _copy_and_traverse.scanned += 1  # type: ignore[attr-defined]
                    if _copy_and_traverse.scanned > self._max_scanned:  # type: ignore[attr-defined]
                        guardrail_hit = True
                        diagnostics.warn(
                            "redactor",
                            "max keys scanned exceeded during string truncation",
                            path=".".join(path_parts),
                        )
                        return copy

                    current_path = [*path_parts, str(key)]
                    value = copy[key]

                    if isinstance(value, str):
                        assert self._max_len is not None  # ensured by early return
                        if len(value) > self._max_len:
                            copy[key] = value[: self._max_len] + self._marker
                            self.last_redacted_count += 1
                            diagnostics.warn(
                                "redactor",
                                "string field truncated",
                                path=".".join(current_path),
                                original_length=len(value),
                                truncated_to=self._max_len,
                            )
                    elif isinstance(value, (dict, list)):
                        copy[key] = _copy_and_traverse(
                            value,
                            depth + 1,
                            current_path,
                        )
                        if guardrail_hit and self._on_guardrail_exceeded == "drop":
                            return copy
                return copy

            elif isinstance(container, list):
                lst = list(container)
                for i, item in enumerate(lst):
                    if isinstance(item, str):
                        assert self._max_len is not None
                        if len(item) > self._max_len:
                            lst[i] = item[: self._max_len] + self._marker
                            self.last_redacted_count += 1
                            diagnostics.warn(
                                "redactor",
                                "string field truncated",
                                path=".".join([*path_parts, f"[{i}]"]),
                                original_length=len(item),
                                truncated_to=self._max_len,
                            )
                    elif isinstance(item, (dict, list)):
                        lst[i] = _copy_and_traverse(item, depth + 1, path_parts)
                        if guardrail_hit and self._on_guardrail_exceeded == "drop":
                            return lst
                return lst

            return container

        _copy_and_traverse.scanned = 0  # type: ignore[attr-defined]
        root: dict = _copy_and_traverse(event, 0, [])

        if guardrail_hit and self._on_guardrail_exceeded == "drop":
            return dict(event)

        return root

    async def health_check(self) -> bool:
        return self._max_depth > 0 and self._max_scanned > 0


PLUGIN_METADATA = {
    "name": "string_truncate",
    "version": "1.0.0",
    "plugin_type": "redactor",
    "entry_point": "fapilog.plugins.redactors.string_truncate:StringTruncateRedactor",
    "description": "Truncates string values exceeding a configurable length.",
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "0.3.0"},
    "config_schema": {
        "type": "object",
        "properties": {
            "max_string_length": {"type": ["integer", "null"]},
            "max_depth": {"type": "integer"},
            "max_keys_scanned": {"type": "integer"},
            "on_guardrail_exceeded": {
                "type": "string",
                "enum": ["warn", "drop"],
            },
        },
    },
    "default_config": {
        "max_string_length": None,
        "max_depth": 16,
        "max_keys_scanned": 1000,
        "on_guardrail_exceeded": "warn",
    },
    "api_version": "1.0",
}

# Mark as referenced for static analyzers (vulture)
_VULTURE_USED: tuple[object] = (StringTruncateRedactor,)
