from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from ...core import diagnostics
from ...metrics.metrics import MetricsCollector


@dataclass
class SizeGuardConfig:
    """Configuration for SizeGuardProcessor."""

    max_bytes: int = 256_000
    action: Literal["truncate", "drop", "warn"] = "truncate"
    preserve_fields: list[str] = field(
        default_factory=lambda: ["level", "timestamp", "logger", "correlation_id"]
    )


class SizeGuardProcessor:
    """Enforce maximum serialized payload size before sinks run."""

    name = "size_guard"

    def __init__(
        self,
        *,
        config: SizeGuardConfig | dict | None = None,
        metrics: MetricsCollector | None = None,
    ) -> None:
        if isinstance(config, dict):
            cfg = SizeGuardConfig(**config.get("config", config))
        elif config is None:
            cfg = SizeGuardConfig()
        else:
            cfg = config

        raw_max = int(getattr(cfg, "max_bytes", 0))
        self._config_valid = raw_max > 0
        self._max_bytes = raw_max if raw_max > 0 else 0
        action = str(getattr(cfg, "action", "truncate")).lower()
        self._action = action if action in {"truncate", "drop", "warn"} else "truncate"
        self._preserve_fields = set(getattr(cfg, "preserve_fields", []) or [])
        self._metrics = metrics
        self._truncated_count = 0
        self._dropped_count = 0

    async def start(self) -> None:  # pragma: no cover - lifecycle hook
        return None

    async def stop(self) -> None:  # pragma: no cover - lifecycle hook
        return None

    async def process(self, view: memoryview) -> memoryview:
        size = len(view)
        if not self._config_valid or size <= self._max_bytes:
            return view

        if self._action == "warn":
            self._emit_warning(size, "size_guard warning pass-through")
            return view

        if self._action == "drop":
            await self._record_dropped()
            self._emit_warning(size, "size_guard dropping oversized payload")
            return self._create_drop_marker(size)

        # Default: truncate
        truncated = self._truncate_payload(view, size)
        await self._record_truncated()
        self._emit_warning(size, "size_guard truncating oversized payload")
        return truncated

    async def health_check(self) -> bool:
        return bool(self._config_valid and self._max_bytes > 0)

    def _emit_warning(self, original_size: int, message: str) -> None:
        try:
            diagnostics.warn(
                "processor",
                message,
                processor="size_guard",
                original_size=original_size,
                max_bytes=self._max_bytes,
                action=self._action,
                _rate_limit_key="size_guard",
            )
        except Exception:
            return

    def _create_drop_marker(self, original_size: int) -> memoryview:
        marker = {
            "_dropped": True,
            "_reason": "payload_size_exceeded",
            "_original_size": original_size,
            "_max_bytes": self._max_bytes,
        }
        return memoryview(self._encode(marker))

    def _truncate_payload(self, view: memoryview, original_size: int) -> memoryview:
        try:
            data = json.loads(bytes(view))
        except Exception:
            return self._create_drop_marker(original_size)

        data["_truncated"] = True
        data["_original_size"] = original_size

        encoded = self._encode(data)
        if len(encoded) <= self._max_bytes:
            return memoryview(encoded)

        data = self._truncate_field(data, "message")
        encoded = self._encode(data)
        if len(encoded) <= self._max_bytes:
            return memoryview(encoded)

        data = self._prune_metadata(data)
        encoded = self._encode(data)
        if len(encoded) <= self._max_bytes:
            return memoryview(encoded)

        data = self._keep_only_preserved(data, original_size)
        encoded = self._encode(data)
        return memoryview(encoded)

    def _truncate_field(self, data: dict[str, Any], field: str) -> dict[str, Any]:
        value = data.get(field)
        if not isinstance(value, str):
            return data

        encoded = self._encode(data)
        if len(encoded) <= self._max_bytes:
            return data

        excess = len(encoded) - self._max_bytes
        keep = max(32, len(value) - excess - 8)
        data[field] = f"{value[:keep]}...[truncated]"
        return data

    def _prune_metadata(self, data: dict[str, Any]) -> dict[str, Any]:
        metadata = data.get("metadata")
        if not isinstance(metadata, dict):
            return data

        sorted_keys = sorted(
            metadata.keys(), key=lambda k: len(str(metadata[k])), reverse=True
        )
        for key in sorted_keys:
            if key in self._preserve_fields:
                continue
            metadata.pop(key, None)
            encoded = self._encode(data)
            if len(encoded) <= self._max_bytes:
                break

        data["metadata"] = metadata
        return data

    def _keep_only_preserved(
        self, data: dict[str, Any], original_size: int
    ) -> dict[str, Any]:
        minimal: dict[str, Any] = {
            "_truncated": True,
            "_original_size": original_size,
            "_heavily_truncated": True,
        }
        for field_name in self._preserve_fields:
            if field_name in data:
                minimal[field_name] = data[field_name]

        if "metadata" in data and isinstance(data["metadata"], dict):
            preserved_meta = {
                k: v for k, v in data["metadata"].items() if k in self._preserve_fields
            }
            if preserved_meta:
                minimal["metadata"] = preserved_meta
        return minimal

    def _encode(self, obj: Any) -> bytes:
        return json.dumps(obj, default=str, separators=(",", ":")).encode("utf-8")

    async def _record_truncated(self) -> None:
        self._truncated_count += 1
        if self._metrics is None:
            return
        try:
            await self._metrics.record_size_guard_truncated()
        except Exception:
            return

    async def _record_dropped(self) -> None:
        self._dropped_count += 1
        if self._metrics is None:
            return
        try:
            await self._metrics.record_size_guard_dropped()
        except Exception:
            return


PLUGIN_METADATA = {
    "name": "size_guard",
    "version": "1.0.0",
    "plugin_type": "processor",
    "entry_point": "fapilog.plugins.processors.size_guard:SizeGuardProcessor",
    "description": "Enforces maximum payload size for downstream compatibility.",
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "0.3.0"},
    "api_version": "1.0",
    "config_schema": {
        "type": "object",
        "properties": {
            "max_bytes": {"type": "integer", "default": 256000},
            "action": {"type": "string", "enum": ["truncate", "drop", "warn"]},
            "preserve_fields": {"type": "array", "items": {"type": "string"}},
        },
    },
    "default_config": {
        "max_bytes": 256000,
        "action": "truncate",
        "preserve_fields": ["level", "timestamp", "logger", "correlation_id"],
    },
}
