"""Field blocker redactor for stripping high-risk field names from events.

Replaces known dangerous field names (e.g., body, request_body, payload) with a
configurable marker anywhere in the event tree. Emits a policy_violation
diagnostic for each blocked field.

This redactor performs field-name checks only (no content scanning), making it
cheap to run. It uses the same depth/scan guardrails as other redactors.

Story 4.69: High-Risk Field Blocking Redactor
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ...core import diagnostics
from ..utils import parse_plugin_config

DEFAULT_BLOCKED_FIELDS = frozenset(
    {
        "body",
        "request_body",
        "response_body",
        "payload",
        "raw",
        "dump",
        "raw_body",
        "raw_request",
        "raw_response",
    }
)


class FieldBlockerConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)

    blocked_fields: list[str] = Field(
        default_factory=lambda: list(DEFAULT_BLOCKED_FIELDS)
    )
    allowed_fields: list[str] = Field(default_factory=list)
    replacement: str = "[REDACTED:HIGH_RISK_FIELD]"
    max_depth: int = Field(default=16, ge=1)
    max_keys_scanned: int = Field(default=1000, ge=1)
    on_guardrail_exceeded: Literal["warn", "drop"] = "warn"


class FieldBlockerRedactor:
    name = "field_blocker"

    def __init__(
        self,
        *,
        config: FieldBlockerConfig | dict | None = None,
        core_max_depth: int | None = None,
        core_max_keys_scanned: int | None = None,
        **kwargs: Any,
    ) -> None:
        cfg = parse_plugin_config(FieldBlockerConfig, config, **kwargs)

        # Pre-compute effective blocklist: blocked - allowed (case-insensitive)
        blocked = frozenset(f.lower() for f in cfg.blocked_fields)
        allowed = frozenset(f.lower() for f in cfg.allowed_fields)
        self._effective_blocklist: frozenset[str] = blocked - allowed

        self._replacement = cfg.replacement
        self._on_guardrail_exceeded = cfg.on_guardrail_exceeded

        # Apply "more restrictive wins" logic for guardrails
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
        root: dict[str, Any] = dict(event)
        self.last_policy_violations = 0

        # Cache as locals for faster lookup in tight loop
        blocklist = self._effective_blocklist
        replacement = self._replacement
        max_depth = self._max_depth
        max_scanned = self._max_scanned
        on_drop = self._on_guardrail_exceeded == "drop"

        scanned = 0
        guardrail_hit = False

        def _walk(obj: Any, depth: int, parent_path: str) -> None:
            nonlocal scanned, guardrail_hit

            if depth > max_depth:
                guardrail_hit = True
                diagnostics.warn(
                    "redactor",
                    "max depth exceeded during field blocking",
                    path=parent_path,
                )
                return

            if isinstance(obj, dict):
                for key in obj:
                    scanned += 1
                    if scanned > max_scanned:
                        guardrail_hit = True
                        diagnostics.warn(
                            "redactor",
                            "max keys scanned exceeded during field blocking",
                            path=parent_path,
                        )
                        return

                    if key.lower() in blocklist:
                        obj[key] = replacement
                        self.last_policy_violations += 1
                        diagnostics.warn(
                            "redactor",
                            "high-risk field blocked",
                            field=str(key),
                            path=f"{parent_path}.{key}" if parent_path else str(key),
                            policy_violation=True,
                        )
                    else:
                        val = obj[key]
                        if isinstance(val, (dict, list)):
                            child_path = (
                                f"{parent_path}.{key}" if parent_path else str(key)
                            )
                            _walk(val, depth + 1, child_path)
                            if guardrail_hit and on_drop:
                                return

            elif isinstance(obj, list):
                for item in obj:
                    if isinstance(item, (dict, list)):
                        _walk(item, depth + 1, parent_path)
                        if guardrail_hit and on_drop:
                            return

        _walk(root, 0, "")

        if guardrail_hit and on_drop:
            return dict(event)

        return root

    async def health_check(self) -> bool:
        return self._max_depth > 0 and self._max_scanned > 0


PLUGIN_METADATA = {
    "name": "field_blocker",
    "version": "1.0.0",
    "plugin_type": "redactor",
    "entry_point": "fapilog.plugins.redactors.field_blocker:FieldBlockerRedactor",
    "description": "Blocks high-risk field names by replacing their values.",
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "0.3.0"},
    "config_schema": {
        "type": "object",
        "properties": {
            "blocked_fields": {"type": "array"},
            "allowed_fields": {"type": "array"},
            "replacement": {"type": "string"},
            "max_depth": {"type": "integer"},
            "max_keys_scanned": {"type": "integer"},
            "on_guardrail_exceeded": {
                "type": "string",
                "enum": ["warn", "drop"],
            },
        },
    },
    "default_config": {
        "blocked_fields": list(DEFAULT_BLOCKED_FIELDS),
        "allowed_fields": [],
        "replacement": "[REDACTED:HIGH_RISK_FIELD]",
        "max_depth": 16,
        "max_keys_scanned": 1000,
        "on_guardrail_exceeded": "warn",
    },
    "api_version": "1.0",
}

# Mark as referenced for static analyzers (vulture)
_VULTURE_USED: tuple[object] = (FieldBlockerRedactor,)
