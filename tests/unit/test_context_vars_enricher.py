import sys
from types import ModuleType

import pytest

from fapilog.core.errors import request_id_var, set_error_context, user_id_var
from fapilog.plugins.enrichers.context_vars import ContextVarsEnricher


@pytest.mark.asyncio
async def test_enrich_includes_request_user_and_tenant() -> None:
    # Set context vars
    set_error_context(request_id="req-123", user_id="u-456")
    enricher = ContextVarsEnricher()
    result = await enricher.enrich({"tenant_id": "t-789"})

    assert result.get("request_id") == "req-123"
    assert result.get("user_id") == "u-456"
    assert result.get("tenant_id") == "t-789"


@pytest.mark.asyncio
async def test_enrich_handles_missing_vars_and_no_tenant() -> None:
    # Clear context vars by setting to None-like via .set on ContextVar
    # ContextVar has no clear; we set different token values in isolation.
    request_id_var.set(None)  # type: ignore[arg-type]
    user_id_var.set(None)  # type: ignore[arg-type]

    enricher = ContextVarsEnricher()
    result = await enricher.enrich({})

    assert "request_id" not in result
    assert "user_id" not in result
    assert "tenant_id" not in result


@pytest.mark.asyncio
async def test_enrich_survives_context_var_get_exceptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    # Should not include request_id/user_id due to exceptions, still include tenant
    assert result.get("tenant_id") == "t-1"
    assert "request_id" not in result
    assert "user_id" not in result


@pytest.mark.asyncio
async def test_enrich_includes_otlp_trace_and_span_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        # Hex strings, zero-padded to 32/16 chars
        assert result.get("trace_id").endswith("1234abcd")
        assert len(result.get("trace_id")) == 32
        assert result.get("span_id").endswith("abcd1234")
        assert len(result.get("span_id")) == 16
    finally:
        # cleanup fake modules
        sys.modules.pop("opentelemetry.trace", None)
        sys.modules.pop("opentelemetry", None)
