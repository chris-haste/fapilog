"""Tests for serialized fallback redaction.

Story 4.54: Redaction Fail-Closed Mode and Fallback Hardening
AC4 & AC5: Serialized payloads are redacted on fallback path.
"""

from __future__ import annotations

import io
import sys
from typing import Any
from unittest.mock import patch

import pytest


class TestSerializedFallbackRedaction:
    """AC4: Serialized fallback path applies minimal redaction."""

    @pytest.fixture
    def capture_stderr(self) -> io.StringIO:
        """Capture stderr output."""
        captured = io.StringIO()
        return captured

    def test_serialized_dict_redacted_on_minimal_mode(
        self, capture_stderr: io.StringIO
    ) -> None:
        """Serialized dict payload has sensitive fields redacted."""
        from fapilog.core.serialization import SerializedView
        from fapilog.plugins.sinks.fallback import _write_to_stderr

        payload = SerializedView(data=b'{"password": "secret123", "user": "alice"}')

        with patch.object(sys, "stderr", capture_stderr):
            _write_to_stderr(payload, serialized=True, redact_mode="minimal")

        output = capture_stderr.getvalue()
        assert "secret123" not in output
        assert '"password"' in output  # Key present
        assert "alice" in output  # Non-sensitive value preserved

    def test_serialized_nested_secrets_redacted(
        self, capture_stderr: io.StringIO
    ) -> None:
        """Nested sensitive fields in serialized payload are redacted."""
        from fapilog.core.serialization import SerializedView
        from fapilog.plugins.sinks.fallback import _write_to_stderr

        payload = SerializedView(
            data=b'{"user": {"password": "hunter2", "name": "bob"}, "api_key": "key123"}'
        )

        with patch.object(sys, "stderr", capture_stderr):
            _write_to_stderr(payload, serialized=True, redact_mode="minimal")

        output = capture_stderr.getvalue()
        assert "hunter2" not in output
        assert "key123" not in output
        assert "bob" in output  # Non-sensitive nested value preserved

    def test_serialized_non_dict_passes_through(
        self, capture_stderr: io.StringIO
    ) -> None:
        """Non-dict JSON (e.g., array) passes through without error."""
        from fapilog.core.serialization import SerializedView
        from fapilog.plugins.sinks.fallback import _write_to_stderr

        payload = SerializedView(data=b'["item1", "item2"]')

        with patch.object(sys, "stderr", capture_stderr):
            _write_to_stderr(payload, serialized=True, redact_mode="minimal")

        output = capture_stderr.getvalue()
        assert "item1" in output
        assert "item2" in output

    def test_redact_mode_none_passes_raw_serialized(
        self, capture_stderr: io.StringIO
    ) -> None:
        """With redact_mode='none', serialized payload is written as-is."""
        from fapilog.core.serialization import SerializedView
        from fapilog.plugins.sinks.fallback import _write_to_stderr

        payload = SerializedView(data=b'{"password": "secret123"}')

        with patch.object(sys, "stderr", capture_stderr):
            _write_to_stderr(payload, serialized=True, redact_mode="none")

        output = capture_stderr.getvalue()
        # With none mode, secret should be present (raw output)
        assert "secret123" in output


class TestInvalidJsonFallback:
    """AC5: Invalid JSON in serialized fallback handled gracefully."""

    @pytest.fixture
    def capture_stderr(self) -> io.StringIO:
        """Capture stderr output."""
        return io.StringIO()

    def test_invalid_json_falls_back_to_raw_with_warning(
        self, capture_stderr: io.StringIO
    ) -> None:
        """Invalid JSON falls back to raw output with diagnostic warning."""
        from fapilog.core.serialization import SerializedView
        from fapilog.plugins.sinks.fallback import _write_to_stderr

        payload = SerializedView(data=b"not valid json {{{")

        diagnostics_called = False
        original_warn: Any = None

        def mock_warn(*args: Any, **kwargs: Any) -> None:
            nonlocal diagnostics_called
            diagnostics_called = True
            # Call original if available
            if original_warn:
                try:
                    original_warn(*args, **kwargs)
                except Exception:
                    pass

        with patch.object(sys, "stderr", capture_stderr):
            from fapilog.core import diagnostics

            original_warn = diagnostics.warn
            with patch.object(diagnostics, "warn", mock_warn):
                _write_to_stderr(payload, serialized=True, redact_mode="minimal")

        output = capture_stderr.getvalue()
        # Should write raw bytes
        assert "not valid json" in output
        # Diagnostic should have been called
        assert diagnostics_called

    def test_binary_payload_handled_gracefully(
        self, capture_stderr: io.StringIO
    ) -> None:
        """Binary (non-UTF8) payload is handled without crashing."""
        from fapilog.core.serialization import SerializedView
        from fapilog.plugins.sinks.fallback import _write_to_stderr

        # Invalid UTF-8 sequence
        payload = SerializedView(data=b"\xff\xfe invalid utf8")

        with patch.object(sys, "stderr", capture_stderr):
            # Should not raise
            _write_to_stderr(payload, serialized=True, redact_mode="minimal")

        output = capture_stderr.getvalue()
        # Should have written something (with replacement chars)
        assert len(output) > 0


class TestExtractBytesHelper:
    """Test _extract_bytes helper function."""

    def test_extract_from_serialized_view(self) -> None:
        """Extracts bytes from SerializedView."""
        from fapilog.core.serialization import SerializedView
        from fapilog.plugins.sinks.fallback import _extract_bytes

        view = SerializedView(data=b"test data")
        result = _extract_bytes(view)
        assert result == b"test data"

    def test_extract_from_memoryview(self) -> None:
        """Extracts bytes from memoryview."""
        from fapilog.plugins.sinks.fallback import _extract_bytes

        data = b"test data"
        mv = memoryview(data)
        result = _extract_bytes(mv)
        assert result == b"test data"

    def test_extract_from_bytes(self) -> None:
        """Extracts bytes from bytes object."""
        from fapilog.plugins.sinks.fallback import _extract_bytes

        data = b"test data"
        result = _extract_bytes(data)
        assert result == b"test data"

    def test_extract_from_bytearray(self) -> None:
        """Extracts bytes from bytearray."""
        from fapilog.plugins.sinks.fallback import _extract_bytes

        data = bytearray(b"test data")
        result = _extract_bytes(data)
        assert result == b"test data"

    def test_extract_from_string_fallback(self) -> None:
        """Falls back to encoding string as UTF-8."""
        from fapilog.plugins.sinks.fallback import _extract_bytes

        result = _extract_bytes("test string")
        assert result == b"test string"
