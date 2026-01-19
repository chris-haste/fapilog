"""
Type contract tests verifying TypedDict definitions match runtime behavior.

These tests ensure the TypedDict definitions in schema.py accurately represent
the actual structure produced by build_envelope() and consumed by serialize_envelope().
"""

from __future__ import annotations

import pytest

from fapilog.core.envelope import build_envelope
from fapilog.core.schema import LogContext, LogDiagnostics, LogEnvelopeV1

pytestmark = pytest.mark.contract


class TestTypeContract:
    """Tests verifying type definitions match runtime structure."""

    def test_build_envelope_returns_typed_structure(self) -> None:
        """build_envelope() output matches LogEnvelopeV1 structure."""
        envelope = build_envelope(level="INFO", message="test")

        # Verify all required fields are present
        assert "timestamp" in envelope
        assert "level" in envelope
        assert "message" in envelope
        assert "logger" in envelope
        assert "context" in envelope
        assert "diagnostics" in envelope
        assert "data" in envelope

        # Verify types match TypedDict expectations
        assert isinstance(envelope["timestamp"], str)
        assert isinstance(envelope["level"], str)
        assert isinstance(envelope["message"], str)
        assert isinstance(envelope["logger"], str)
        assert isinstance(envelope["context"], dict)
        assert isinstance(envelope["diagnostics"], dict)
        assert isinstance(envelope["data"], dict)

    def test_context_fields_match_type_definition(self) -> None:
        """Context dict fields match LogContext structure."""
        envelope = build_envelope(
            level="INFO",
            message="test",
            bound_context={
                "request_id": "req-123",
                "user_id": "user-456",
                "tenant_id": "tenant-789",
                "trace_id": "trace-abc",
                "span_id": "span-def",
            },
            correlation_id="corr-xyz",
        )

        context = envelope["context"]
        # All context fields defined in LogContext should be strings
        assert isinstance(context.get("correlation_id"), str)
        assert isinstance(context.get("request_id"), str)
        assert isinstance(context.get("user_id"), str)
        assert isinstance(context.get("tenant_id"), str)
        assert isinstance(context.get("trace_id"), str)
        assert isinstance(context.get("span_id"), str)

    def test_diagnostics_fields_match_type_definition(self) -> None:
        """Diagnostics dict fields match LogDiagnostics structure."""
        try:
            raise ValueError("test error")
        except ValueError:
            envelope = build_envelope(
                level="ERROR",
                message="error",
                exc_info=True,
            )

        diagnostics = envelope["diagnostics"]
        # Exception should be a dict when present
        if "exception" in diagnostics:
            assert isinstance(diagnostics["exception"], dict)

    def test_data_field_accepts_arbitrary_values(self) -> None:
        """Data dict accepts arbitrary JSON-serializable values."""
        envelope = build_envelope(
            level="INFO",
            message="test",
            extra={
                "string_val": "hello",
                "int_val": 42,
                "float_val": 3.14,
                "bool_val": True,
                "list_val": [1, 2, 3],
                "dict_val": {"nested": "value"},
                "none_val": None,
            },
        )

        data = envelope["data"]
        assert data["string_val"] == "hello"
        assert data["int_val"] == 42
        assert data["float_val"] == 3.14
        assert data["bool_val"] is True
        assert data["list_val"] == [1, 2, 3]
        assert data["dict_val"] == {"nested": "value"}
        assert data["none_val"] is None

    def test_typed_dict_can_be_used_for_type_checking(self) -> None:
        """TypedDict definitions can be used for static type checking."""
        # This test verifies the types are importable and usable
        # Actual static type checking is done by mypy

        # Verify LogEnvelopeV1 has expected keys (runtime check)
        expected_keys = {
            "timestamp",
            "level",
            "message",
            "logger",
            "context",
            "diagnostics",
            "data",
        }
        # TypedDict __annotations__ contains the field types
        assert set(LogEnvelopeV1.__annotations__.keys()) == expected_keys

        # Verify LogContext has expected keys
        context_keys = {
            "correlation_id",
            "request_id",
            "user_id",
            "tenant_id",
            "trace_id",
            "span_id",
        }
        assert set(LogContext.__annotations__.keys()) == context_keys

        # Verify LogDiagnostics has expected keys
        diagnostics_keys = {"service", "env", "host", "pid", "exception"}
        assert set(LogDiagnostics.__annotations__.keys()) == diagnostics_keys
