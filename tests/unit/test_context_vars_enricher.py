import sys
from types import ModuleType

import pytest

from fapilog.core.errors import request_id_var, set_error_context, user_id_var
from fapilog.plugins.enrichers.context_vars import ContextVarsEnricher


@pytest.mark.asyncio
async def test_returns_context_structure() -> None:
    """ContextVarsEnricher returns nested structure targeting context group."""
    set_error_context(request_id="req-123", user_id="u-456")
    enricher = ContextVarsEnricher()
    result = await enricher.enrich({})

    assert "context" in result
    assert isinstance(result["context"], dict)
    # Should not have flat top-level context fields
    assert "request_id" not in result
    assert "user_id" not in result


@pytest.mark.asyncio
async def test_context_contains_request_id_user_id() -> None:
    """Context group contains request/user identifiers."""
    set_error_context(request_id="req-123", user_id="u-456")
    enricher = ContextVarsEnricher()
    result = await enricher.enrich({})

    ctx = result["context"]
    assert ctx["request_id"] == "req-123"
    assert ctx["user_id"] == "u-456"


@pytest.mark.asyncio
async def test_enrich_includes_tenant_in_context() -> None:
    """Tenant ID from event is included in context group."""
    set_error_context(request_id="req-123", user_id="u-456")
    enricher = ContextVarsEnricher()
    result = await enricher.enrich({"tenant_id": "t-789"})

    ctx = result["context"]
    assert ctx["request_id"] == "req-123"
    assert ctx["user_id"] == "u-456"
    assert ctx["tenant_id"] == "t-789"


@pytest.mark.asyncio
async def test_enrich_handles_missing_vars_and_no_tenant() -> None:
    """Empty context returned when no context vars are set."""
    # Clear context vars by setting to None-like via .set on ContextVar
    request_id_var.set(None)  # type: ignore[arg-type]
    user_id_var.set(None)  # type: ignore[arg-type]

    enricher = ContextVarsEnricher()
    result = await enricher.enrich({})

    assert "context" in result
    ctx = result["context"]
    assert "request_id" not in ctx
    assert "user_id" not in ctx
    assert "tenant_id" not in ctx


@pytest.mark.asyncio
async def test_enrich_survives_context_var_get_exceptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enricher continues even when context var access raises."""

    class BrokenVar:
        def get(self, default=None):  # type: ignore[no-untyped-def]
            raise RuntimeError("boom")

    monkeypatch.setattr(
        "fapilog.plugins.enrichers.context_vars.request_id_var", BrokenVar()
    )
    monkeypatch.setattr(
        "fapilog.plugins.enrichers.context_vars.user_id_var", BrokenVar()
    )

    enricher = ContextVarsEnricher()
    result = await enricher.enrich({"tenant_id": "t-1"})

    # Should still return context structure with tenant
    assert "context" in result
    ctx = result["context"]
    assert ctx["tenant_id"] == "t-1"
    assert "request_id" not in ctx
    assert "user_id" not in ctx


@pytest.mark.asyncio
async def test_context_contains_trace_span_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Context group includes OpenTelemetry trace/span IDs when available."""
    # Create fake opentelemetry.trace module
    fake_otel = ModuleType("opentelemetry")
    fake_trace = ModuleType("opentelemetry.trace")

    class FakeSpanContext:
        def __init__(self) -> None:
            self._valid = True
            self.trace_id = int("1234abcd", 16)
            self.span_id = int("abcd1234", 16)

        def is_valid(self):  # type: ignore[no-untyped-def]
            return self._valid

    class FakeSpan:
        def get_span_context(self):  # type: ignore[no-untyped-def]
            return FakeSpanContext()

    def get_current_span():  # type: ignore[no-untyped-def]
        return FakeSpan()

    fake_trace.get_current_span = get_current_span  # type: ignore[attr-defined]
    sys.modules["opentelemetry"] = fake_otel
    sys.modules["opentelemetry.trace"] = fake_trace

    try:
        enricher = ContextVarsEnricher()
        result = await enricher.enrich({})

        assert "context" in result
        ctx = result["context"]
        # Hex strings, zero-padded to 32/16 chars
        assert ctx["trace_id"].endswith("1234abcd")
        assert len(ctx["trace_id"]) == 32
        assert ctx["span_id"].endswith("abcd1234")
        assert len(ctx["span_id"]) == 16
    finally:
        # cleanup fake modules
        sys.modules.pop("opentelemetry.trace", None)
        sys.modules.pop("opentelemetry", None)
