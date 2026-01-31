"""Tests for log origin tracking (Story 10.48).

Verifies that logs from different sources have appropriate origin values
in the diagnostics section of the envelope.
"""

from __future__ import annotations

import pytest


class TestNativeLogsHaveOrigin:
    """AC1: Logs created directly with fapilog loggers have origin: 'native'."""

    def test_build_envelope_defaults_to_native_origin(self) -> None:
        """build_envelope() should set origin='native' by default."""
        from fapilog.core.envelope import build_envelope

        envelope = build_envelope(level="INFO", message="test message")

        assert envelope["diagnostics"]["origin"] == "native"

    def test_build_envelope_origin_in_diagnostics_section(self) -> None:
        """origin field should be in the diagnostics section, not elsewhere."""
        from fapilog.core.envelope import build_envelope

        envelope = build_envelope(level="INFO", message="test")

        # origin is in diagnostics
        assert "origin" in envelope["diagnostics"]
        # origin is not at the top level or in other sections
        assert "origin" not in envelope
        assert "origin" not in envelope["context"]
        assert "origin" not in envelope["data"]


class TestStdlibBridgeLogsHaveOrigin:
    """AC2: Logs routed through stdlib bridge have origin: 'stdlib'."""

    def test_build_envelope_accepts_origin_parameter(self) -> None:
        """build_envelope() should accept explicit origin parameter."""
        from fapilog.core.envelope import build_envelope

        envelope = build_envelope(
            level="INFO",
            message="stdlib log",
            origin="stdlib",
        )

        assert envelope["diagnostics"]["origin"] == "stdlib"


class TestExplicitOriginOverride:
    """AC3: Users can explicitly set origin for edge cases."""

    def test_build_envelope_accepts_third_party_origin(self) -> None:
        """build_envelope() should accept origin='third_party'."""
        from fapilog.core.envelope import build_envelope

        envelope = build_envelope(
            level="INFO",
            message="sdk event",
            origin="third_party",
        )

        assert envelope["diagnostics"]["origin"] == "third_party"


class TestOriginInSerializedOutput:
    """Verify origin is present in serialized log output."""

    def test_origin_serializes_to_json(self) -> None:
        """origin field should be present in serialized JSON output."""
        import json

        from fapilog.core.envelope import build_envelope
        from fapilog.core.serialization import serialize_envelope

        envelope = build_envelope(level="INFO", message="test")
        serialized = serialize_envelope(envelope)
        # SerializedView wraps the envelope in {"log": ..., "schema_version": ...}
        parsed = json.loads(serialized.data)

        assert parsed["log"]["diagnostics"]["origin"] == "native"


class TestSchemaTypeIncludesOrigin:
    """AC6: LogDiagnostics TypedDict includes origin."""

    def test_log_diagnostics_has_origin_key(self) -> None:
        """LogDiagnostics TypedDict should include origin field."""
        from typing import get_type_hints

        from fapilog.core.schema import LogDiagnostics

        hints = get_type_hints(LogDiagnostics)

        assert "origin" in hints

    def test_log_origin_type_exists(self) -> None:
        """LogOrigin type should be defined in schema module."""
        from typing import get_args

        from fapilog.core.schema import LogOrigin

        # LogOrigin should be a Literal type with the three valid values
        valid_values = get_args(LogOrigin)
        assert set(valid_values) == {"native", "stdlib", "third_party"}


class TestOriginTypeSafety:
    """Verify origin type constraints."""

    @pytest.mark.parametrize(
        "origin",
        ["native", "stdlib", "third_party"],
    )
    def test_valid_origin_values_accepted(self, origin: str) -> None:
        """All documented origin values should work."""
        from typing import cast

        from fapilog.core.envelope import build_envelope
        from fapilog.core.schema import LogOrigin

        envelope = build_envelope(
            level="INFO", message="test", origin=cast(LogOrigin, origin)
        )

        assert envelope["diagnostics"]["origin"] == origin


class TestStdlibBridgeOrigin:
    """AC2: Stdlib bridge sets origin='stdlib' on routed logs."""

    def test_stdlib_bridge_handler_emits_stdlib_origin(self) -> None:
        """StdlibBridgeHandler should call logger with origin='stdlib'."""
        import logging
        from unittest.mock import MagicMock

        from fapilog.core.stdlib_bridge import StdlibBridgeHandler

        # Create a mock fapilog logger
        mock_logger = MagicMock()
        mock_logger.info = MagicMock(return_value=None)

        handler = StdlibBridgeHandler(mock_logger)

        # Create a log record
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="test message",
            args=(),
            exc_info=None,
        )

        handler.emit(record)

        # Verify _origin='stdlib' was passed
        mock_logger.info.assert_called_once()
        call_kwargs = mock_logger.info.call_args.kwargs
        assert call_kwargs.get("_origin") == "stdlib"


class TestLoggerOriginParameter:
    """AC3: Logger methods accept _origin parameter for explicit override."""

    @pytest.mark.asyncio
    async def test_logger_prepare_payload_passes_origin_to_envelope(self) -> None:
        """_origin parameter in metadata should be passed to build_envelope."""
        from typing import Any
        from unittest.mock import patch

        from fapilog.core.envelope import build_envelope as real_build
        from fapilog.core.logger import SyncLoggerFacade

        captured_origin: list[Any] = []

        def capture_build(*args: Any, **kwargs: Any) -> Any:
            captured_origin.append(kwargs.get("origin"))
            return real_build(*args, **kwargs)

        async def mock_sink(entry: dict[str, Any]) -> None:
            pass

        logger = SyncLoggerFacade(
            name="test",
            queue_capacity=10,
            batch_max_size=5,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=mock_sink,
        )

        with patch("fapilog.core.logger.build_envelope") as mock_build:
            mock_build.side_effect = capture_build

            # Call with _origin parameter
            logger._prepare_payload("INFO", "test", _origin="third_party")

        assert captured_origin == ["third_party"]

    @pytest.mark.asyncio
    async def test_logger_defaults_to_native_origin(self) -> None:
        """Logger should default to origin='native' when _origin not specified."""
        from typing import Any
        from unittest.mock import patch

        from fapilog.core.envelope import build_envelope as real_build
        from fapilog.core.logger import SyncLoggerFacade

        captured_origin: list[Any] = []

        def capture_build(*args: Any, **kwargs: Any) -> Any:
            captured_origin.append(kwargs.get("origin"))
            return real_build(*args, **kwargs)

        async def mock_sink(entry: dict[str, Any]) -> None:
            pass

        logger = SyncLoggerFacade(
            name="test",
            queue_capacity=10,
            batch_max_size=5,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=mock_sink,
        )

        with patch("fapilog.core.logger.build_envelope") as mock_build:
            mock_build.side_effect = capture_build

            # Call without _origin parameter
            logger._prepare_payload("INFO", "test")

        # Should default to native
        assert captured_origin == ["native"]
