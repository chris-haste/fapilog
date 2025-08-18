"""
Regex-based redactor for masking event fields whose dot-paths match patterns.

Behavior mirrors FieldMaskRedactor semantics:
 - Idempotent masking: values already equal to mask_string remain unchanged
 - Preserves event shape; masks values, not keys
 - Traverses dicts and lists; list indices are transparent in the path
 - Guardrails: max recursion depth and max keys scanned
 - Structured diagnostics via core.diagnostics.warn; never raises upstream

Configuration fields:
 - patterns: list[str] of regex patterns matched against dot-joined field paths
 - mask_string: str token used to replace matched values (default: "***")
 - block_on_unredactable: bool for diagnostics when path cannot be redacted
 - max_depth: int recursion guard (default: 16)
 - max_keys_scanned: int scan guard (default: 1000)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from ...core import diagnostics


@dataclass
class RegexMaskConfig:
    patterns: list[str]
    mask_string: str = "***"
    block_on_unredactable: bool = False
    max_depth: int = 16
    max_keys_scanned: int = 1000


class RegexMaskRedactor:
    name = "regex-mask"

    def __init__(self, *, config: RegexMaskConfig | None = None) -> None:
        cfg = config or RegexMaskConfig(patterns=[])
        # Pre-compile patterns for performance; use fullmatch semantics by
        # default
        self._patterns: list[re.Pattern[str]] = [re.compile(p) for p in cfg.patterns]
        self._mask = str(cfg.mask_string)
        self._block = bool(cfg.block_on_unredactable)
        self._max_depth = int(cfg.max_depth)
        self._max_scanned = int(cfg.max_keys_scanned)

    async def start(self) -> None:  # pragma: no cover - optional lifecycle
        return None

    async def stop(self) -> None:  # pragma: no cover - optional lifecycle
        return None

    async def redact(self, event: dict) -> dict:
        # Work on a shallow copy of the root; mutate nested containers in
        # place
        root: dict[str, Any] = dict(event)
        self._apply_regex_masks(root)
        return root

    def _apply_regex_masks(self, root: dict[str, Any]) -> None:
        scanned = 0

        def mask_scalar(value: Any) -> Any:
            # Idempotence: do not double-mask
            if isinstance(value, str) and value == self._mask:
                return value
            return self._mask

        def path_matches(path_segments: Iterable[str]) -> bool:
            if not self._patterns:
                return False
            path_str = ".".join(path_segments)
            for pat in self._patterns:
                try:
                    if pat.fullmatch(path_str):
                        return True
                except Exception:
                    # Defensive: ignore a broken pattern at runtime
                    continue
            return False

        def traverse(container: Any, current_path: list[str], depth: int) -> None:
            nonlocal scanned
            if depth > self._max_depth:
                diagnostics.warn(
                    "redactor",
                    "max depth exceeded during regex redaction",
                    path=".".join(current_path),
                )
                return
            if scanned > self._max_scanned:
                diagnostics.warn(
                    "redactor",
                    "max keys scanned exceeded during regex redaction",
                    path=".".join(current_path),
                )
                return

            if isinstance(container, dict):
                for key in list(container.keys()):
                    scanned += 1
                    path_next = current_path + [str(key)]
                    try:
                        if path_matches(path_next):
                            # Terminal mask at this path
                            try:
                                container[key] = mask_scalar(container.get(key))
                            except Exception:
                                if self._block:
                                    diagnostics.warn(
                                        "redactor",
                                        "unredactable terminal field",
                                        reason="assignment failed",
                                        path=".".join(path_next),
                                    )
                            # Do not descend further when masked
                            continue
                    except Exception:
                        # Continue traversal even if match check failed
                        pass

                    value = container.get(key)
                    if isinstance(value, (dict, list)):
                        traverse(value, path_next, depth + 1)
                    # Primitives are left as-is unless matched above

            elif isinstance(container, list):
                # For lists, indices are transparent in path semantics
                for item in container:
                    scanned += 1
                    traverse(item, current_path, depth + 1)
            else:
                # Primitive encountered; nothing to traverse
                return

        traverse(root, [], 0)


# Minimal built-in PLUGIN_METADATA for optional discovery of core redactor
PLUGIN_METADATA = {
    "name": "regex-mask",
    "version": "1.0.0",
    "plugin_type": "redactor",
    "entry_point": "fapilog.plugins.redactors.regex_mask:RegexMaskRedactor",
    "description": (
        "Masks values for fields whose dot-paths match configured regex patterns."
    ),
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "3.0.0"},
    "config_schema": {
        "type": "object",
        "properties": {
            "patterns": {"type": "array"},
            "mask_string": {"type": "string"},
            "block_on_unredactable": {"type": "boolean"},
            "max_depth": {"type": "integer"},
            "max_keys_scanned": {"type": "integer"},
        },
        "required": ["patterns"],
    },
    "default_config": {
        "patterns": [],
        "mask_string": "***",
        "block_on_unredactable": False,
        "max_depth": 16,
        "max_keys_scanned": 1000,
    },
    "api_version": "1.0",
}

# Mark as referenced for static analyzers (vulture)
_VULTURE_USED: tuple[object] = (RegexMaskRedactor,)
