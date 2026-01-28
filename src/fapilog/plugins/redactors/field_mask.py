from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ...core import diagnostics
from ..utils import parse_plugin_config


class FieldMaskConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)

    fields_to_mask: list[str] = Field(default_factory=list)
    mask_string: str = "***"
    block_on_unredactable: bool = True
    max_depth: int = Field(default=16, ge=1)
    max_keys_scanned: int = Field(default=1000, ge=1)
    on_guardrail_exceeded: Literal["warn", "drop", "replace_subtree"] = (
        "replace_subtree"
    )


class FieldMaskRedactor:
    name = "field_mask"

    def __init__(
        self,
        *,
        config: FieldMaskConfig | dict | None = None,
        core_max_depth: int | None = None,
        core_max_keys_scanned: int | None = None,
        **kwargs: Any,
    ) -> None:
        cfg = parse_plugin_config(FieldMaskConfig, config, **kwargs)
        # Normalize
        self._fields: list[list[str]] = [
            [seg for seg in path.split(".") if seg]
            for path in (cfg.fields_to_mask or [])
        ]
        self._mask = str(cfg.mask_string)
        self._block = bool(cfg.block_on_unredactable)

        # Apply "more restrictive wins" logic for guardrails
        # Core guardrails override plugin settings when more restrictive
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

        self._on_guardrail_exceeded = cfg.on_guardrail_exceeded

    async def start(self) -> None:  # pragma: no cover - optional
        return None

    async def stop(self) -> None:  # pragma: no cover - optional
        return None

    async def redact(self, event: dict) -> dict | None:
        # Work on a shallow copy of the root; mutate nested containers in place
        root: dict[str, Any] = dict(event)
        for path in self._fields:
            guardrail_hit = self._apply_mask(root, path)
            if guardrail_hit and self._on_guardrail_exceeded == "drop":
                return None
        return root

    def _apply_mask(self, root: dict[str, Any], path: list[str]) -> bool:
        """Apply mask to path in root. Returns True if guardrail was hit."""
        scanned = 0
        guardrail_hit = False

        def mask_scalar(value: Any) -> Any:
            # Idempotence: do not double-mask
            if isinstance(value, str) and value == self._mask:
                return value
            return self._mask

        def _handle_guardrail(
            parent: dict | list | None, parent_key: str | int | None, reason: str
        ) -> None:
            nonlocal guardrail_hit
            diagnostics.warn(
                "redactor",
                reason,
                path=".".join(path),
            )
            guardrail_hit = True
            if (
                self._on_guardrail_exceeded == "replace_subtree"
                and parent is not None
                and parent_key is not None
            ):
                parent[parent_key] = self._mask  # type: ignore[index]

        def _traverse(
            container: Any,
            seg_idx: int,
            depth: int,
            parent: dict | list | None = None,
            parent_key: str | int | None = None,
        ) -> None:
            nonlocal scanned, guardrail_hit
            if depth > self._max_depth:
                _handle_guardrail(
                    parent, parent_key, "max depth exceeded during redaction"
                )
                return
            if scanned > self._max_scanned:
                _handle_guardrail(
                    parent, parent_key, "max keys scanned exceeded during redaction"
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
                            _traverse(v, seg_idx + 1, depth + 1, container, k)
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
                                _traverse(
                                    nxt_candidate,
                                    seg_idx + 1,
                                    depth + 1,
                                    container,
                                    base_key,
                                )
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
                        # Check depth BEFORE recursing - if next level would exceed, replace
                        # current container (not the child we're about to enter)
                        if depth + 1 > self._max_depth:
                            _handle_guardrail(
                                parent,
                                parent_key,
                                "max depth exceeded during redaction",
                            )
                            return
                        _traverse(nxt, seg_idx + 1, depth + 1, container, key)
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
                    for i, item in enumerate(container):
                        scanned += 1
                        _traverse(item, seg_idx + 1, depth + 1, container, i)
                    return
                # Numeric index if provided
                if key.isdigit():
                    idx = int(key)
                    if 0 <= idx < len(container):
                        scanned += 1
                        _traverse(
                            container[idx], seg_idx + 1, depth + 1, container, idx
                        )
                    return
                # Default: propagate same index level for all items
                for i, item in enumerate(container):
                    scanned += 1
                    _traverse(item, seg_idx, depth + 1, container, i)
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
        return guardrail_hit

    async def health_check(self) -> bool:
        """Verify redactor configuration is valid.

        Checks that field paths are parsed and guardrails are positive.
        """
        try:
            # Verify configuration is valid
            if self._max_depth <= 0 or self._max_scanned <= 0:
                return False
            # Verify mask string is not empty
            if not self._mask:
                return False
            return True
        except Exception:
            return False


# Minimal built-in PLUGIN_METADATA for optional discovery of core redactor
PLUGIN_METADATA = {
    "name": "field_mask",
    "version": "1.0.0",
    "plugin_type": "redactor",
    "entry_point": "fapilog.plugins.redactors.field_mask:FieldMaskRedactor",
    "description": "Masks configured fields in structured events.",
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "0.3.0"},
    "config_schema": {
        "type": "object",
        "properties": {
            "fields_to_mask": {"type": "array"},
            "mask_string": {"type": "string"},
            "block_on_unredactable": {"type": "boolean"},
            "max_depth": {"type": "integer"},
            "max_keys_scanned": {"type": "integer"},
            "on_guardrail_exceeded": {
                "type": "string",
                "enum": ["warn", "drop", "replace_subtree"],
            },
        },
        "required": ["fields_to_mask"],
    },
    "default_config": {
        "fields_to_mask": [],
        "mask_string": "***",
        "block_on_unredactable": True,
        "max_depth": 16,
        "max_keys_scanned": 1000,
        "on_guardrail_exceeded": "replace_subtree",
    },
    "api_version": "1.0",
}
