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
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field

from ...core import diagnostics
from ..utils import parse_plugin_config

# ReDoS detection patterns - identify common catastrophic backtracking constructs
_REDOS_DETECTORS = [
    (re.compile(r"\([^)]*[+*][^)]*\)[+*]"), "nested quantifier"),
    (re.compile(r"\([^)]*\|[^)]*\)[+*]"), "alternation with quantifier"),
    (re.compile(r"\.\*[^)]*\)\{[0-9]+,"), "wildcard in bounded repetition"),
]


def _is_potentially_dangerous(pattern: str) -> str | None:
    """Check if a regex pattern contains potentially dangerous ReDoS constructs.

    Args:
        pattern: The regex pattern string to check.

    Returns:
        A reason string if the pattern is potentially dangerous, None if safe.
    """
    for detector, reason in _REDOS_DETECTORS:
        if detector.search(pattern):
            return reason
    return None


class RegexMaskConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)

    patterns: list[str] = Field(default_factory=list)
    mask_string: str = "***"
    block_on_unredactable: bool = False
    max_depth: int = Field(default=16, ge=1)
    max_keys_scanned: int = Field(default=1000, ge=1)
    allow_unsafe_patterns: bool = Field(
        default=False,
        description="Bypass ReDoS pattern validation. Use with caution.",
    )


class RegexMaskRedactor:
    name = "regex_mask"

    def __init__(
        self,
        *,
        config: RegexMaskConfig | dict | None = None,
        core_max_depth: int | None = None,
        core_max_keys_scanned: int | None = None,
        **kwargs: Any,
    ) -> None:
        cfg = parse_plugin_config(RegexMaskConfig, config, **kwargs)
        # Pre-compile patterns for performance; track any failures
        self._patterns: list[re.Pattern[str]] = []
        self._pattern_errors: list[str] = []

        allow_unsafe = bool(cfg.allow_unsafe_patterns)
        for p in cfg.patterns:
            # Check for ReDoS-vulnerable patterns unless escape hatch is enabled
            if not allow_unsafe:
                danger_reason = _is_potentially_dangerous(p)
                if danger_reason:
                    self._pattern_errors.append(f"{p}: {danger_reason}")
                    continue

            try:
                self._patterns.append(re.compile(p))
            except re.error as e:
                self._pattern_errors.append(f"{p}: {e}")

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

    async def health_check(self) -> bool:
        """Verify all regex patterns compiled successfully.

        Returns False if any pattern failed to compile.
        """
        try:
            # Check no pattern compilation errors
            if self._pattern_errors:
                return False
            # Verify guardrails are positive
            if self._max_depth <= 0 or self._max_scanned <= 0:
                return False
            return True
        except Exception:
            return False


# Minimal built-in PLUGIN_METADATA for optional discovery of core redactor
PLUGIN_METADATA = {
    "name": "regex_mask",
    "version": "1.0.0",
    "plugin_type": "redactor",
    "entry_point": "fapilog.plugins.redactors.regex_mask:RegexMaskRedactor",
    "description": (
        "Masks values for fields whose dot-paths match configured regex patterns."
    ),
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "0.3.0"},
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
