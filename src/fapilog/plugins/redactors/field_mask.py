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
                # Support wildcard for dict/list segment: "*" or "[*]"
                if key in ("*", "[*]"):
                    for k, v in list(container.items()):
                        scanned += 1
                        if seg_idx == len(path) - 1:
                            try:
                                container[k] = mask_scalar(v)
                            except Exception:
                                if self._block:
                                    diagnostics.warn(
                                        "redactor",
                                        "unredactable terminal field",
                                        reason="assignment failed",
                                        path=".".join(path),
                                    )
                            continue
                        if isinstance(v, (dict, list)):
                            _traverse(v, seg_idx + 1, depth + 1)
                    return
                # Support dict key with wildcard suffix, e.g., "users[*]"
                if key.endswith("[*]") and len(key) > 3:
                    base_key = key[:-3]
                    if base_key in container:
                        nxt_candidate = container.get(base_key)
                        if seg_idx == len(path) - 1:
                            # Terminal wildcard: mask each element/value
                            if isinstance(nxt_candidate, list):
                                for i, v in enumerate(list(nxt_candidate)):
                                    scanned += 1
                                    try:
                                        nxt_candidate[i] = mask_scalar(v)
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
                                # Non-list under wildcard; treat as absent
                                return
                        else:
                            # Descend into list under base_key
                            if isinstance(nxt_candidate, (list, dict)):
                                _traverse(nxt_candidate, seg_idx + 1, depth + 1)
                            return
                # Numeric index semantics if key is int string
                if key.isdigit():
                    # Not applicable for dicts; ignore
                    return
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
                if key in ("*", "[*]"):
                    for item in container:
                        scanned += 1
                        _traverse(item, seg_idx + 1, depth + 1)
                    return
                # Numeric index if provided
                if key.isdigit():
                    idx = int(key)
                    if 0 <= idx < len(container):
                        scanned += 1
                        _traverse(container[idx], seg_idx + 1, depth + 1)
                    return
                # Default: propagate same index level for all items
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
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "3.0.0"},
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
    "api_version": "1.0",
}
