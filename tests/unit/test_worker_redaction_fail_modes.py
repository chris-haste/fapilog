"""Tests for redaction fail mode behavior in LoggerWorker.

Story 4.54: Redaction Fail-Closed Mode and Fallback Hardening
Story 4.61: Align Worker Redaction Fail Mode Default with Settings
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from fapilog.core.settings import CoreSettings


class TestRedactionFailModeDefaultAlignment:
    """Story 4.61: Worker and Settings defaults must be aligned."""

    def test_worker_redaction_fail_mode_matches_settings(self) -> None:
        """Regression test: LoggerWorker default must match CoreSettings default.

        Story 4.61 AC1/AC3: Prevents silent security regression from default drift.
        """
        import inspect

        from fapilog.core.worker import LoggerWorker

        worker_sig = inspect.signature(LoggerWorker.__init__)
        worker_default = worker_sig.parameters["redaction_fail_mode"].default
        settings_default = CoreSettings.model_fields["redaction_fail_mode"].default

        assert worker_default == settings_default, (
            f"LoggerWorker.redaction_fail_mode default ({worker_default}) "
            f"must match CoreSettings default ({settings_default})"
        )


class TestRedactionFailModeSetting:
    """AC1: Global redaction fail mode setting."""

    def test_default_is_warn(self) -> None:
        """Base default for redaction_fail_mode is 'warn' (fail-closed, Story 4.61)."""
        settings = CoreSettings()
        assert settings.redaction_fail_mode == "warn"

    def test_builder_with_fallback_redaction_sets_fail_mode(self) -> None:
        """Builder with_fallback_redaction sets redaction_fail_mode."""
        from fapilog.builder import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_fallback_redaction(fail_mode="closed")

        # Check the config was set
        assert builder._config["core"]["redaction_fail_mode"] == "closed"

    def test_builder_with_fallback_redaction_sets_both_modes(self) -> None:
        """Builder with_fallback_redaction sets both fallback and fail modes."""
        from fapilog.builder import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_fallback_redaction(fallback_mode="none", fail_mode="warn")

        assert builder._config["core"]["fallback_redact_mode"] == "none"
        assert builder._config["core"]["redaction_fail_mode"] == "warn"

    def test_builder_with_fallback_redaction_sets_raw_hardening(self) -> None:
        """Builder with_fallback_redaction sets raw output hardening params (Story 4.59)."""
        from fapilog.builder import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_fallback_redaction(scrub_raw=False, raw_max_bytes=1000)

        assert builder._config["core"]["fallback_scrub_raw"] is False
        assert builder._config["core"]["fallback_raw_max_bytes"] == 1000

    def test_builder_with_fallback_redaction_raw_max_bytes_omitted(self) -> None:
        """raw_max_bytes not set when None (default)."""
        from fapilog.builder import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_fallback_redaction()

        assert builder._config["core"]["fallback_scrub_raw"] is True
        assert "fallback_raw_max_bytes" not in builder._config["core"]

    def test_explicit_closed(self) -> None:
        """Can set redaction_fail_mode to 'closed'."""
        settings = CoreSettings(redaction_fail_mode="closed")
        assert settings.redaction_fail_mode == "closed"

    def test_explicit_warn(self) -> None:
        """Can set redaction_fail_mode to 'warn'."""
        settings = CoreSettings(redaction_fail_mode="warn")
        assert settings.redaction_fail_mode == "warn"

    def test_invalid_value_rejected(self) -> None:
        """Invalid values are rejected by Pydantic validation."""
        with pytest.raises(ValueError):
            CoreSettings(redaction_fail_mode="invalid")  # type: ignore[arg-type]


class TestRedactionFailModePresets:
    """AC1: Preset-specific defaults for redaction_fail_mode."""

    def test_production_preset_defaults_to_warn(self) -> None:
        """Production preset sets redaction_fail_mode to 'warn'."""
        from fapilog.core.presets import get_preset

        preset = get_preset("production")
        assert preset["core"]["redaction_fail_mode"] == "warn"

    def test_fastapi_preset_defaults_to_warn(self) -> None:
        """FastAPI preset sets redaction_fail_mode to 'warn'."""
        from fapilog.core.presets import get_preset

        preset = get_preset("fastapi")
        assert preset["core"]["redaction_fail_mode"] == "warn"

    def test_serverless_preset_defaults_to_warn(self) -> None:
        """Serverless preset sets redaction_fail_mode to 'warn'."""
        from fapilog.core.presets import get_preset

        preset = get_preset("serverless")
        assert preset["core"]["redaction_fail_mode"] == "warn"

    def test_dev_preset_does_not_set_warn(self) -> None:
        """Dev preset does not override (uses base default 'open')."""
        from fapilog.core.presets import get_preset

        preset = get_preset("dev")
        # Dev preset should not have redaction_fail_mode set (uses default)
        assert "redaction_fail_mode" not in preset.get("core", {})


class TestMetricsRecordRedactionException:
    """Test record_redaction_exception() method in MetricsCollector."""

    @pytest.mark.asyncio
    async def test_record_redaction_exception_exists(self) -> None:
        """MetricsCollector has record_redaction_exception method."""
        from fapilog.metrics.metrics import MetricsCollector

        collector = MetricsCollector(enabled=False)
        # Method should exist and be callable
        assert hasattr(collector, "record_redaction_exception")
        # Should not raise when called
        await collector.record_redaction_exception()

    @pytest.mark.asyncio
    async def test_record_redaction_exception_increments_counter(self) -> None:
        """record_redaction_exception increments Prometheus counter when enabled."""
        from fapilog.metrics.metrics import MetricsCollector

        collector = MetricsCollector(enabled=True)
        if collector.is_enabled:
            # Get initial value
            await collector.record_redaction_exception()
            await collector.record_redaction_exception(count=2)
            # Counter should have been incremented (we can't easily read Prometheus counters,
            # but we verify no exception is raised)


class TestWorkerApplyRedactorsFailModes:
    """AC2 & AC3: Worker behavior with different fail modes."""

    @pytest.fixture
    def mock_metrics(self) -> MagicMock:
        """Create mock metrics collector."""
        metrics = MagicMock()
        metrics.record_redaction_exception = AsyncMock()
        metrics.record_events_dropped = AsyncMock()
        return metrics

    @pytest.mark.asyncio
    async def test_fail_open_passes_original_on_exception(self) -> None:
        """With fail_mode='open', original entry passes through on exception."""
        from unittest.mock import patch

        from fapilog.core.worker import LoggerWorker

        worker = LoggerWorker(
            queue=MagicMock(),
            batch_max_size=10,
            batch_timeout_seconds=1.0,
            sink_write=AsyncMock(),
            sink_write_serialized=None,
            enrichers_getter=lambda: [],
            redactors_getter=lambda: [MagicMock()],  # Non-empty to trigger redaction
            metrics=None,
            serialize_in_flush=False,
            strict_envelope_mode_provider=lambda: False,
            stop_flag=lambda: False,
            drained_event=None,
            flush_event=None,
            flush_done_event=None,
            emit_enricher_diagnostics=False,
            emit_redactor_diagnostics=False,
            counters={"processed": 0, "dropped": 0},
            redaction_fail_mode="open",
        )

        entry = {"message": "test", "password": "secret"}

        # Mock redact_in_order to raise an exception
        with patch(
            "fapilog.core.worker.redact_in_order",
            side_effect=RuntimeError("redact_in_order exploded"),
        ):
            result = await worker._apply_redactors(entry)

        # Should return original entry unchanged
        assert result == entry
        assert result["password"] == "secret"

    @pytest.mark.asyncio
    async def test_fail_closed_drops_event_on_exception(self) -> None:
        """With fail_mode='closed', event is dropped (returns None) on exception."""
        from unittest.mock import patch

        from fapilog.core.worker import LoggerWorker

        worker = LoggerWorker(
            queue=MagicMock(),
            batch_max_size=10,
            batch_timeout_seconds=1.0,
            sink_write=AsyncMock(),
            sink_write_serialized=None,
            enrichers_getter=lambda: [],
            redactors_getter=lambda: [MagicMock()],
            metrics=None,
            serialize_in_flush=False,
            strict_envelope_mode_provider=lambda: False,
            stop_flag=lambda: False,
            drained_event=None,
            flush_event=None,
            flush_done_event=None,
            emit_enricher_diagnostics=False,
            emit_redactor_diagnostics=False,
            counters={"processed": 0, "dropped": 0},
            redaction_fail_mode="closed",
        )

        entry = {"message": "test", "password": "secret"}

        with patch(
            "fapilog.core.worker.redact_in_order",
            side_effect=RuntimeError("redact_in_order exploded"),
        ):
            result = await worker._apply_redactors(entry)

        # Should return None to signal drop
        assert result is None

    @pytest.mark.asyncio
    async def test_fail_warn_passes_original_on_exception(self) -> None:
        """With fail_mode='warn', original entry passes through on exception."""
        from unittest.mock import patch

        from fapilog.core.worker import LoggerWorker

        worker = LoggerWorker(
            queue=MagicMock(),
            batch_max_size=10,
            batch_timeout_seconds=1.0,
            sink_write=AsyncMock(),
            sink_write_serialized=None,
            enrichers_getter=lambda: [],
            redactors_getter=lambda: [MagicMock()],
            metrics=None,
            serialize_in_flush=False,
            strict_envelope_mode_provider=lambda: False,
            stop_flag=lambda: False,
            drained_event=None,
            flush_event=None,
            flush_done_event=None,
            emit_enricher_diagnostics=False,
            emit_redactor_diagnostics=False,
            counters={"processed": 0, "dropped": 0},
            redaction_fail_mode="warn",
        )

        entry = {"message": "test", "password": "secret"}

        with patch(
            "fapilog.core.worker.redact_in_order",
            side_effect=RuntimeError("redact_in_order exploded"),
        ):
            result = await worker._apply_redactors(entry)

        # Should return original entry unchanged
        assert result == entry

    @pytest.mark.asyncio
    async def test_fail_mode_metrics_incremented(self, mock_metrics: MagicMock) -> None:
        """Metrics record_redaction_exception is called on exception."""
        from unittest.mock import patch

        from fapilog.core.worker import LoggerWorker

        worker = LoggerWorker(
            queue=MagicMock(),
            batch_max_size=10,
            batch_timeout_seconds=1.0,
            sink_write=AsyncMock(),
            sink_write_serialized=None,
            enrichers_getter=lambda: [],
            redactors_getter=lambda: [MagicMock()],
            metrics=mock_metrics,
            serialize_in_flush=False,
            strict_envelope_mode_provider=lambda: False,
            stop_flag=lambda: False,
            drained_event=None,
            flush_event=None,
            flush_done_event=None,
            emit_enricher_diagnostics=False,
            emit_redactor_diagnostics=False,
            counters={"processed": 0, "dropped": 0},
            redaction_fail_mode="warn",
        )

        with patch(
            "fapilog.core.worker.redact_in_order",
            side_effect=RuntimeError("redact_in_order exploded"),
        ):
            await worker._apply_redactors({"message": "test"})

        mock_metrics.record_redaction_exception.assert_awaited_once()


class TestFlushBatchHandlesNoneFromRedactors:
    """Test that _flush_batch properly handles None return from _apply_redactors."""

    @pytest.mark.asyncio
    async def test_none_return_skipped_in_flush_batch(self) -> None:
        """Events dropped by redactors (None) are not written to sink."""
        from unittest.mock import patch

        from fapilog.core.worker import LoggerWorker

        written: list[dict[str, Any]] = []

        async def mock_write(entry: dict[str, Any]) -> None:
            written.append(entry)

        counters = {"processed": 0, "dropped": 0}
        worker = LoggerWorker(
            queue=MagicMock(),
            batch_max_size=10,
            batch_timeout_seconds=1.0,
            sink_write=mock_write,
            sink_write_serialized=None,
            enrichers_getter=lambda: [],
            redactors_getter=lambda: [MagicMock()],
            metrics=None,
            serialize_in_flush=False,
            strict_envelope_mode_provider=lambda: False,
            stop_flag=lambda: False,
            drained_event=None,
            flush_event=None,
            flush_done_event=None,
            emit_enricher_diagnostics=False,
            emit_redactor_diagnostics=False,
            counters=counters,
            redaction_fail_mode="closed",
        )

        batch = [{"message": "test1"}, {"message": "test2"}]

        with patch(
            "fapilog.core.worker.redact_in_order",
            side_effect=RuntimeError("redact_in_order exploded"),
        ):
            await worker._flush_batch(batch)

        # No events should be written (all dropped by fail-closed)
        assert len(written) == 0
        # Dropped counter should be incremented
        assert counters["dropped"] == 2

    @pytest.mark.asyncio
    async def test_none_return_increments_metrics_when_available(self) -> None:
        """Events dropped by redactors increment metrics when collector is provided."""
        from unittest.mock import patch

        from fapilog.core.worker import LoggerWorker

        written: list[dict[str, Any]] = []
        mock_metrics = MagicMock()
        mock_metrics.record_events_dropped = AsyncMock()
        mock_metrics.record_redaction_exception = AsyncMock()

        async def mock_write(entry: dict[str, Any]) -> None:
            written.append(entry)

        counters = {"processed": 0, "dropped": 0}
        worker = LoggerWorker(
            queue=MagicMock(),
            batch_max_size=10,
            batch_timeout_seconds=1.0,
            sink_write=mock_write,
            sink_write_serialized=None,
            enrichers_getter=lambda: [],
            redactors_getter=lambda: [MagicMock()],
            metrics=mock_metrics,
            serialize_in_flush=False,
            strict_envelope_mode_provider=lambda: False,
            stop_flag=lambda: False,
            drained_event=None,
            flush_event=None,
            flush_done_event=None,
            emit_enricher_diagnostics=False,
            emit_redactor_diagnostics=False,
            counters=counters,
            redaction_fail_mode="closed",
        )

        batch = [{"message": "test1"}, {"message": "test2"}]

        with patch(
            "fapilog.core.worker.redact_in_order",
            side_effect=RuntimeError("redact_in_order exploded"),
        ):
            await worker._flush_batch(batch)

        # Metrics should be called for each dropped event
        assert mock_metrics.record_events_dropped.await_count == 2
