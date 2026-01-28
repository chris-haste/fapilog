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


class TestRawOutputScrubbing:
    """Story 4.59: Fallback Sink Raw Output Hardening.

    When JSON parsing fails for serialized payloads, apply keyword scrubbing
    and optional truncation before writing to stderr.
    """

    @pytest.fixture
    def capture_stderr(self) -> io.StringIO:
        """Capture stderr output."""
        return io.StringIO()

    def test_raw_output_scrubs_password_patterns(
        self, capture_stderr: io.StringIO
    ) -> None:
        """AC1: Raw fallback output scrubs password=value patterns."""
        from fapilog.core.serialization import SerializedView
        from fapilog.plugins.sinks.fallback import _write_to_stderr

        # Invalid JSON containing password pattern
        payload = SerializedView(data=b"login failed: password=hunter2&user=alice")

        with patch.object(sys, "stderr", capture_stderr):
            _write_to_stderr(payload, serialized=True, redact_mode="minimal")

        output = capture_stderr.getvalue()
        assert "hunter2" not in output
        assert "password=***" in output
        assert "alice" in output  # Non-sensitive value preserved

    def test_raw_output_scrubs_token_patterns(
        self, capture_stderr: io.StringIO
    ) -> None:
        """AC1: Raw fallback output scrubs token/api_key/secret patterns."""
        from fapilog.core.serialization import SerializedView
        from fapilog.plugins.sinks.fallback import _write_to_stderr

        # Invalid JSON containing various secret patterns
        payload = SerializedView(
            data=b"token=abc123 api_key:sk_live_xyz secret=mysecret auth:bearer123"
        )

        with patch.object(sys, "stderr", capture_stderr):
            _write_to_stderr(payload, serialized=True, redact_mode="minimal")

        output = capture_stderr.getvalue()
        assert "abc123" not in output
        assert "sk_live_xyz" not in output
        assert "mysecret" not in output
        assert "bearer123" not in output
        assert "token=***" in output
        assert "api_key:***" in output

    def test_raw_output_truncation(self, capture_stderr: io.StringIO) -> None:
        """AC2: Unparseable payloads truncated when fallback_raw_max_bytes set."""
        from fapilog.core.serialization import SerializedView
        from fapilog.plugins.sinks.fallback import _write_to_stderr

        # Create a large invalid JSON payload (5KB)
        large_content = b"x" * 5000
        payload = SerializedView(data=large_content)

        with patch.object(sys, "stderr", capture_stderr):
            _write_to_stderr(
                payload,
                serialized=True,
                redact_mode="minimal",
                fallback_raw_max_bytes=1000,
            )

        output = capture_stderr.getvalue()
        # Should be truncated with marker
        assert "[truncated]" in output
        # Actual content should be limited (1000 bytes + truncation marker + newline)
        assert len(output) < 1100

    def test_scrub_disabled_via_setting(self, capture_stderr: io.StringIO) -> None:
        """AC4: Scrubbing can be disabled for debugging."""
        from fapilog.core.serialization import SerializedView
        from fapilog.plugins.sinks.fallback import _write_to_stderr

        # Invalid JSON with password
        payload = SerializedView(data=b"debug: password=hunter2")

        with patch.object(sys, "stderr", capture_stderr):
            _write_to_stderr(
                payload,
                serialized=True,
                redact_mode="minimal",
                fallback_scrub_raw=False,
            )

        output = capture_stderr.getvalue()
        # With scrubbing disabled, secret should be present
        assert "hunter2" in output

    def test_diagnostic_includes_scrub_info(self, capture_stderr: io.StringIO) -> None:
        """AC5: Diagnostic warning includes scrubbed/truncated/original_size info."""
        from fapilog.core.serialization import SerializedView
        from fapilog.plugins.sinks.fallback import _write_to_stderr

        payload = SerializedView(data=b"password=secret123 " + b"x" * 2000)
        warn_kwargs: dict[str, Any] = {}

        def capture_warn(*args: Any, **kwargs: Any) -> None:
            nonlocal warn_kwargs
            warn_kwargs = kwargs

        with patch.object(sys, "stderr", capture_stderr):
            from fapilog.core import diagnostics

            with patch.object(diagnostics, "warn", capture_warn):
                _write_to_stderr(
                    payload,
                    serialized=True,
                    redact_mode="minimal",
                    fallback_raw_max_bytes=1000,
                )

        # Diagnostic should include scrub/truncate info
        assert warn_kwargs.get("scrubbed") is True
        assert warn_kwargs.get("truncated") is True
        assert warn_kwargs.get("original_size") > 0


class TestFallbackScrubPatterns:
    """Test FALLBACK_SCRUB_PATTERNS regex patterns directly."""

    def test_patterns_exist(self) -> None:
        """FALLBACK_SCRUB_PATTERNS is defined in defaults."""
        from fapilog.core.defaults import FALLBACK_SCRUB_PATTERNS

        assert len(FALLBACK_SCRUB_PATTERNS) > 0

    def test_password_pattern_variants(self) -> None:
        """Password pattern handles various formats."""
        from fapilog.plugins.sinks.fallback import _scrub_raw

        test_cases = [
            ("password=secret", "password=***"),
            ("passwd=secret", "passwd=***"),
            ("pwd:secret", "pwd:***"),
            ("PASSWORD=Secret123", "PASSWORD=***"),
        ]
        for input_text, expected in test_cases:
            result = _scrub_raw(input_text)
            assert expected in result, f"Failed for {input_text}"

    def test_token_pattern_variants(self) -> None:
        """Token/key patterns handle various formats."""
        from fapilog.plugins.sinks.fallback import _scrub_raw

        test_cases = [
            ("token=abc123", "token=***"),
            ("api_key: xyz", "api_key: ***"),  # Separator whitespace preserved
            ("apikey=key123", "apikey=***"),
            ("secret=mysecret", "secret=***"),
        ]
        for input_text, expected in test_cases:
            result = _scrub_raw(input_text)
            assert expected in result, f"Failed for {input_text}"

    def test_authorization_pattern(self) -> None:
        """Authorization header pattern is scrubbed."""
        from fapilog.plugins.sinks.fallback import _scrub_raw

        result = _scrub_raw("authorization: Bearer eyJ123")
        assert "eyJ123" not in result
        assert "authorization:" in result.lower()


class TestCoreSettingsFallbackRaw:
    """Test fallback raw output settings in CoreSettings."""

    def test_fallback_scrub_raw_default_true(self) -> None:
        """AC3: Default settings have fallback_scrub_raw=True."""
        from fapilog.core.settings import CoreSettings

        settings = CoreSettings()
        assert settings.fallback_scrub_raw is True

    def test_fallback_raw_max_bytes_default_none(self) -> None:
        """Default settings have fallback_raw_max_bytes=None (no truncation)."""
        from fapilog.core.settings import CoreSettings

        settings = CoreSettings()
        assert settings.fallback_raw_max_bytes is None

    def test_fallback_scrub_raw_env_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC4: Can disable scrubbing via environment variable."""
        from fapilog.core.settings import Settings

        monkeypatch.setenv("FAPILOG_CORE__FALLBACK_SCRUB_RAW", "false")
        settings = Settings()
        assert settings.core.fallback_scrub_raw is False

    def test_fallback_raw_max_bytes_configurable(self) -> None:
        """fallback_raw_max_bytes can be configured."""
        from fapilog.core.settings import CoreSettings

        settings = CoreSettings(fallback_raw_max_bytes=1000)
        assert settings.fallback_raw_max_bytes == 1000
