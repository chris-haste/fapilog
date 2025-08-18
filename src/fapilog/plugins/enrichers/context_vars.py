from __future__ import annotations

from typing import Any

from ...core.errors import request_id_var, user_id_var


class ContextVarsEnricher:
    name = "context_vars"

    async def start(self) -> None:  # pragma: no cover - optional
        return None

    async def stop(self) -> None:  # pragma: no cover - optional
        return None

    async def enrich(self, event: dict[str, Any]) -> dict[str, Any]:
        data: dict[str, Any] = {}

        # request_id
        try:
            rid = request_id_var.get(None)
        except Exception:
            rid = None
        if rid is not None:
            data["request_id"] = rid

        # Optional user_id
        try:
            uid = user_id_var.get(None)
        except Exception:
            uid = None
        if uid is not None:
            data["user_id"] = uid

        # Optional OpenTelemetry ids (if OTEL installed)
        try:  # pragma: no cover - environment dependent
            from opentelemetry.trace import get_current_span

            span = get_current_span()
            ctx = getattr(span, "get_span_context", lambda: None)()
            if ctx and getattr(ctx, "is_valid", lambda: False)():
                trace_id = getattr(ctx, "trace_id", None)
                span_id = getattr(ctx, "span_id", None)
                if trace_id is not None:
                    data["trace_id"] = f"{trace_id:032x}"
                if span_id is not None:
                    data["span_id"] = f"{span_id:016x}"
        except Exception:
            pass

        # Optional tenant_id from event (do not overwrite if already present)
        if "tenant_id" in event and "tenant_id" not in data:
            data["tenant_id"] = event.get("tenant_id")

        return data


__all__ = ["ContextVarsEnricher"]

# Minimal PLUGIN_METADATA for discovery
PLUGIN_METADATA = {
    "name": "context-vars-enricher",
    "version": "1.0.0",
    "plugin_type": "enricher",
    "entry_point": "fapilog.plugins.enrichers.context_vars:ContextVarsEnricher",
    "description": "Adds context variables like request_id and user_id when available.",
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "3.0.0"},
    "api_version": "1.0",
}
