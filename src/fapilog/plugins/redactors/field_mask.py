from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...core import diagnostics


@dataclass
class FieldMaskConfig:
    fields_to_mask: list[str]
    mask_string: str = "***"
    block_on_unredactable: bool = False
    max_depth: int = 16
    max_keys_scanned: int = 1000


class FieldMaskRedactor:
    name = "field-mask"

    def __init__(self, *, config: FieldMaskConfig | None = None) -> None:
        cfg = config or FieldMaskConfig(fields_to_mask=[])
        # Normalize
        self._fields: list[list[str]] = [
            [seg for seg in path.split(".") if seg]
            for path in (cfg.fields_to_mask or [])
        ]
        self._mask = str(cfg.mask_string)
        self._block = bool(cfg.block_on_unredactable)
        self._max_depth = int(cfg.max_depth)
        self._max_scanned = int(cfg.max_keys_scanned)

    async def start(self) -> None:  # pragma: no cover - optional
        return None

    async def stop(self) -> None:  # pragma: no cover - optional
        return None

    async def redact(self, event: dict) -> dict:
        # Work on a shallow copy of the root; mutate nested containers in place
        root: dict[str, Any] = dict(event)
        for path in self._fields:
            self._apply_mask(root, path)
        return root

    def _apply_mask(self, root: dict[str, Any], path: list[str]) -> None:
        scanned = 0

        def mask_scalar(value: Any) -> Any:
            # Idempotence: do not double-mask
            if isinstance(value, str) and value == self._mask:
                return value
            return self._mask

        def _traverse(container: Any, seg_idx: int, depth: int) -> None:
            nonlocal scanned
            if depth > self._max_depth:
                diagnostics.warn(
                    "redactor",
                    "max depth exceeded during redaction",
                    path=".".join(path),
                )
                return
            if scanned > self._max_scanned:
                diagnostics.warn(
                    "redactor",
                    "max keys scanned exceeded during redaction",
                    path=".".join(path),
                )
                return

            if seg_idx >= len(path):
                # Nothing to do
                return

            key = path[seg_idx]
            if isinstance(container, dict):
                scanned += 1
                if key not in container:
                    # Absent path: ignore
                    return
                if seg_idx == len(path) - 1:
                    # Terminal: mask value (idempotent)
                    try:
                        container[key] = mask_scalar(container.get(key))
                    except Exception:
                        if self._block:
                            diagnostics.warn(
                                "redactor",
                                "unredactable terminal field",
                                reason="assignment failed",
                                path=".".join(path),
                            )
                        return
                else:
                    nxt = container.get(key)
                    if isinstance(nxt, (dict, list)):
                        _traverse(nxt, seg_idx + 1, depth + 1)
                    else:
                        # Non-container encountered before terminal
                        if self._block:
                            diagnostics.warn(
                                "redactor",
                                "unredactable intermediate field",
                                reason="not dict or list",
                                path=".".join(path),
                            )
                        return
            elif isinstance(container, list):
                # Apply traversal to each element for this segment
                for item in container:
                    scanned += 1
                    _traverse(item, seg_idx, depth + 1)
            else:
                # Primitive encountered mid-path
                if self._block:
                    diagnostics.warn(
                        "redactor",
                        "unredactable container",
                        reason="not dict or list",
                        path=".".join(path),
                    )

        _traverse(root, 0, 0)


# Minimal built-in PLUGIN_METADATA for optional discovery of core redactor
PLUGIN_METADATA = {
    "name": "field-mask",
    "version": "1.0.0",
    "plugin_type": "redactor",
    "entry_point": "fapilog.plugins.redactors.field_mask:FieldMaskRedactor",
    "description": "Masks configured fields in structured events.",
    "author": "Fapilog Core Team",
    "config_schema": {
        "type": "object",
        "properties": {
            "fields_to_mask": {"type": "array"},
            "mask_string": {"type": "string"},
            "block_on_unredactable": {"type": "boolean"},
            "max_depth": {"type": "integer"},
            "max_keys_scanned": {"type": "integer"},
        },
        "required": ["fields_to_mask"],
    },
    "default_config": {
        "fields_to_mask": [],
        "mask_string": "***",
        "block_on_unredactable": False,
        "max_depth": 16,
        "max_keys_scanned": 1000,
    },
}
