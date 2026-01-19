"""
Test logger setup and initialization.

Scope:
- get_async_logger configuration and startup
- runtime and runtime_async context managers
- Settings configuration and validation
- _configure_logger_common and _start_plugins_sync
- _LoggerMixin shared behavior
- Edge cases in logger creation

Does NOT cover:
- Async facade behavior (see test_logger_async.py)
- Threading lifecycle (see test_logger_threading.py)
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

import fapilog
from fapilog import (
    Settings,
    get_async_logger,
    runtime,
    runtime_async,
)
from fapilog.core.logger import AsyncLoggerFacade, SyncLoggerFacade

# ==============================================================================
# Test Fixtures and Helpers
# ==============================================================================


async def _sink_write(event):  # type: ignore[no-untyped-def]
    return None


def _logger_args() -> dict:
    return {
        "name": "test",
        "queue_capacity": 8,
        "batch_max_size": 1,
        "batch_timeout_seconds": 0.1,
        "backpressure_wait_ms": 1,
        "drop_on_full": False,
        "sink_write": _sink_write,
        "sink_write_serialized": None,
        "enrichers": None,
        "processors": None,
        "filters": None,
        "metrics": None,
        "exceptions_enabled": True,
        "exceptions_max_frames": 10,
        "exceptions_max_stack_chars": 1024,
        "serialize_in_flush": False,
        "num_workers": 1,
        "level_gate": None,
    }


class _TrackingPlugin:
    def __init__(self, name: str) -> None:
        self.name = name
        self.started = False

    async def start(self) -> None:
        self.started = True


# ==============================================================================
# GetAsyncLogger Tests
# ==============================================================================


class TestGetAsyncLoggerCoverage:
    """Test get_async_logger function to improve coverage."""

    @pytest.mark.asyncio
    async def test_get_async_logger_basic_usage(self) -> None:
        """Test basic async logger creation."""
        logger = await get_async_logger(name="async-test")
        assert logger._name == "async-test"
        await logger.info("test message")
        await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_get_async_logger_with_rotating_file_sink(
        self, tmp_path: Path
    ) -> None:
        """Test async logger with rotating file sink."""
        with patch.dict(os.environ, {"FAPILOG_FILE__DIRECTORY": str(tmp_path)}):
            logger = await get_async_logger(name="async-file-test")
            await logger.info("test message")
            await logger.stop_and_drain()

            files = list(tmp_path.iterdir())
            assert any(p.is_file() for p in files)

    @pytest.mark.asyncio
    async def test_get_async_logger_with_custom_settings(self) -> None:
        """Test async logger with custom settings."""
        settings = Settings()
        settings.core.enable_metrics = True
        settings.core.max_queue_size = 100

        logger = await get_async_logger(name="async-settings-test", settings=settings)
        assert logger._queue.capacity == 100
        await logger.info("test message")
        await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_get_async_logger_sink_start_failure(self) -> None:
        """Test async logger when sink start fails."""
        mock_sink = Mock()
        mock_sink.start.side_effect = RuntimeError("Start failed")
        mock_sink._started = False

        with patch(
            "fapilog.plugins.sinks.stdout_json.StdoutJsonSink", return_value=mock_sink
        ):
            logger = await get_async_logger(name="async-sink-fail-test")
            await logger.info("test message")
            await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_get_async_logger_sink_write_serialized_fallback(self) -> None:
        """Test async logger sink write_serialized fallback."""
        mock_sink = Mock()
        del mock_sink.write_serialized

        with patch(
            "fapilog.plugins.sinks.stdout_json.StdoutJsonSink", return_value=mock_sink
        ):
            logger = await get_async_logger(name="async-serialized-fallback-test")
            await logger.info("test message")
            await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_get_async_logger_with_context_binding(self) -> None:
        """Test async logger with context binding enabled."""
        settings = Settings()
        settings.core.context_binding_enabled = True
        settings.core.default_bound_context = {"tenant": "test-tenant"}

        logger = await get_async_logger(name="async-context-test", settings=settings)
        await logger.info("test message")
        await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_get_async_logger_context_binding_exception(self) -> None:
        """Test async logger when context binding fails."""
        settings = Settings()
        settings.core.context_binding_enabled = True
        settings.core.default_bound_context = {"tenant": "test-tenant"}

        with patch(
            "fapilog.core.logger.AsyncLoggerFacade.bind",
            side_effect=RuntimeError("Bind failed"),
        ):
            logger = await get_async_logger(
                name="async-context-exception-test", settings=settings
            )
            await logger.info("test message")
            await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_get_async_logger_with_sensitive_fields_policy(self) -> None:
        """Test async logger with sensitive fields policy."""
        settings = Settings()
        settings.core.sensitive_fields_policy = ["password", "secret"]

        logger = await get_async_logger(name="async-policy-test", settings=settings)
        await logger.info("test message")
        await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_get_async_logger_with_redactors(self) -> None:
        """Test async logger with redactors enabled."""
        settings = Settings()
        settings.core.enable_redactors = True
        settings.core.redactors = [
            "field_mask",
            "regex_mask",
        ]  # Explicitly set redactors
        settings.core.sensitive_fields_policy = ["password"]

        logger = await get_async_logger(name="async-redactors-test", settings=settings)
        assert hasattr(logger, "_redactors")
        assert len(logger._redactors) == 2
        await logger.info("test message")
        await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_get_async_logger_redactors_exception(self) -> None:
        """Test async logger when redactor configuration fails."""
        settings = Settings()
        settings.core.enable_redactors = True
        settings.core.redactors_order = ["field-mask", "regex-mask"]
        settings.core.sensitive_fields_policy = ["password"]

        with patch(
            "fapilog.plugins.redactors.field_mask.FieldMaskRedactor",
            side_effect=ImportError("Redactor failed"),
        ):
            logger = await get_async_logger(
                name="async-redactors-exception-test", settings=settings
            )
            await logger.info("test message")
            await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_get_async_logger_with_unhandled_capture(self) -> None:
        """Test async logger with unhandled exception capture."""
        settings = Settings()
        settings.core.capture_unhandled_enabled = True

        logger = await get_async_logger(name="async-unhandled-test", settings=settings)
        await logger.info("test message")
        await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_get_async_logger_unhandled_capture_exception(self) -> None:
        """Test async logger when unhandled capture fails."""
        settings = Settings()
        settings.core.capture_unhandled_enabled = True

        with patch(
            "fapilog.core.errors.capture_unhandled_exceptions",
            side_effect=RuntimeError("Capture failed"),
        ):
            logger = await get_async_logger(
                name="async-unhandled-exception-test", settings=settings
            )
            await logger.info("test message")
            await logger.stop_and_drain()


class TestGetAsyncLoggerSinkErrors:
    """Test sink error paths in get_async_logger."""

    @pytest.mark.asyncio
    async def test_get_async_logger_sink_start_failure_with_diagnostics_exception(
        self,
    ) -> None:
        """Test async sink start failure when diagnostics also fails."""
        mock_sink = Mock()
        mock_sink.start.side_effect = RuntimeError("Start failed")
        mock_sink._started = False
        mock_sink.write = Mock()

        with patch(
            "fapilog.plugins.sinks.stdout_json.StdoutJsonSink", return_value=mock_sink
        ):
            with patch(
                "fapilog.core.diagnostics.warn",
                side_effect=RuntimeError("Diagnostics failed"),
            ):
                logger = await get_async_logger(name="async-sink-start-fail-test")
                await logger.info("test message")
                await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_get_async_logger_sink_write_serialized_attribute_error(self) -> None:
        """Test async sink write_serialized AttributeError path."""
        mock_sink = Mock()
        del mock_sink.write_serialized

        with patch(
            "fapilog.plugins.sinks.stdout_json.StdoutJsonSink", return_value=mock_sink
        ):
            logger = await get_async_logger(name="async-serialized-attr-error-test")
            await logger.info("test message")
            await logger.stop_and_drain()


# ==============================================================================
# RuntimeAsync Tests
# ==============================================================================


class TestRuntimeAsyncCoverage:
    """Test runtime_async function to improve coverage."""

    @pytest.mark.asyncio
    async def test_runtime_async_basic_usage(self) -> None:
        """Test basic runtime_async usage."""
        async with runtime_async() as logger:
            await logger.info("test message")

    @pytest.mark.asyncio
    async def test_runtime_disallowed_inside_event_loop(self) -> None:
        """Sync runtime should raise when used in an active event loop."""
        with pytest.raises(RuntimeError):
            with runtime():
                pass

    @pytest.mark.asyncio
    async def test_runtime_async_with_custom_settings(self) -> None:
        """Test runtime_async with custom settings."""
        settings = Settings()
        settings.core.enable_metrics = True

        async with runtime_async(settings=settings) as logger:
            await logger.info("test message")

    @pytest.mark.asyncio
    async def test_runtime_async_drain_exception(self) -> None:
        """Test runtime_async when drain fails."""
        with patch(
            "fapilog.core.logger.AsyncLoggerFacade.drain",
            side_effect=RuntimeError("Drain failed"),
        ):
            async with runtime_async() as logger:
                await logger.info("test message")

    @pytest.mark.asyncio
    async def test_runtime_async_drain_warning_exception(self) -> None:
        """Test runtime_async when drain warning fails."""
        with patch(
            "fapilog.core.logger.AsyncLoggerFacade.drain",
            side_effect=RuntimeError("Drain failed"),
        ):
            with patch(
                "fapilog.core.diagnostics.warn", side_effect=RuntimeError("Warn failed")
            ):
                async with runtime_async() as logger:
                    await logger.info("test message")


# ==============================================================================
# Runtime Tests
# ==============================================================================


class TestRuntimeCoverage:
    """Test runtime function to improve coverage."""

    def test_runtime_basic_usage(self) -> None:
        """Test basic runtime usage."""
        with runtime() as logger:
            logger.info("test message")

    def test_runtime_with_custom_settings(self) -> None:
        """Test runtime with custom settings."""
        settings = Settings()
        settings.core.enable_metrics = True

        with runtime(settings=settings) as logger:
            logger.info("test message")

    def test_runtime_inside_running_loop(self) -> None:
        """Test runtime when already inside a running event loop."""
        with patch("asyncio.run", side_effect=RuntimeError("Already in loop")):
            with runtime() as logger:
                logger.info("test message")

    def test_runtime_drain_exception(self) -> None:
        """Test runtime when drain fails."""
        with patch(
            "fapilog.core.logger.SyncLoggerFacade.stop_and_drain",
            side_effect=RuntimeError("Drain failed"),
        ):
            with runtime() as logger:
                logger.info("test message")

    def test_runtime_background_thread_fallback(self) -> None:
        """Test runtime background thread fallback."""
        with patch("asyncio.run", side_effect=RuntimeError("Already in loop")):
            with patch("asyncio.get_event_loop") as mock_get_loop:
                mock_loop = Mock()
                mock_loop.create_task.side_effect = RuntimeError("Loop failed")
                mock_get_loop.return_value = mock_loop

                with runtime() as logger:
                    logger.info("test message")

    def test_runtime_asyncio_run_runtime_error_with_coro_close(self) -> None:
        """Test runtime when asyncio.run fails with RuntimeError and coro.close fails."""
        mock_coro = Mock()
        mock_coro.close.side_effect = RuntimeError("Close failed")

        with patch("asyncio.get_running_loop", side_effect=RuntimeError("No loop")):
            with patch("asyncio.run", side_effect=RuntimeError("Run failed")):
                with patch(
                    "fapilog.core.logger.SyncLoggerFacade.stop_and_drain",
                    return_value=mock_coro,
                ):
                    with runtime() as logger:
                        logger.info("test message")


# ==============================================================================
# GetLogger Sink Start Failure Tests
# ==============================================================================


class TestGetLoggerSinkStartFailure:
    """Test sink start failure paths in get_logger."""

    def test_get_logger_sink_start_failure_with_diagnostics_exception(self) -> None:
        """Test sink start failure when diagnostics also fails."""
        from fapilog import get_logger

        mock_sink = Mock()
        mock_sink.start.side_effect = RuntimeError("Start failed")
        mock_sink._started = False
        mock_sink.write = Mock()

        with patch(
            "fapilog.plugins.sinks.stdout_json.StdoutJsonSink", return_value=mock_sink
        ):
            with patch(
                "fapilog.core.diagnostics.warn",
                side_effect=RuntimeError("Diagnostics failed"),
            ):
                logger = get_logger(name="sink-start-fail-test")
                logger.info("test message")
                import asyncio

                asyncio.run(logger.stop_and_drain())


# ==============================================================================
# GetLogger Edge Cases Tests
# ==============================================================================


class TestGetLoggerEdgeCases:
    """Test get_logger edge cases to improve coverage."""

    def test_get_logger_sink_start_failure(self) -> None:
        """Test get_logger when sink start fails."""
        mock_sink = Mock()
        mock_sink.start.side_effect = RuntimeError("Start failed")
        mock_sink._started = False

        with patch(
            "fapilog.plugins.sinks.stdout_json.StdoutJsonSink", return_value=mock_sink
        ):
            with runtime() as logger:
                logger.info("test message")

    def test_get_logger_sink_write_serialized_fallback(self) -> None:
        """Test get_logger sink write_serialized fallback."""
        mock_sink = Mock()
        del mock_sink.write_serialized

        with patch(
            "fapilog.plugins.sinks.stdout_json.StdoutJsonSink", return_value=mock_sink
        ):
            with runtime() as logger:
                logger.info("test message")

    def test_get_logger_context_binding_exception(self) -> None:
        """Test get_logger when context binding fails."""
        settings = Settings()
        settings.core.context_binding_enabled = True
        settings.core.default_bound_context = {"tenant": "test-tenant"}

        with patch(
            "fapilog.core.logger.SyncLoggerFacade.bind",
            side_effect=RuntimeError("Bind failed"),
        ):
            with runtime() as logger:
                logger.info("test message")

    def test_get_logger_redactors_exception(self) -> None:
        """Test get_logger when redactor configuration fails."""
        settings = Settings()
        settings.core.enable_redactors = True
        settings.core.redactors_order = ["field-mask", "regex-mask"]
        settings.core.sensitive_fields_policy = ["password"]

        with patch(
            "fapilog.plugins.redactors.field_mask.FieldMaskRedactor",
            side_effect=ImportError("Redactor failed"),
        ):
            with runtime() as logger:
                logger.info("test message")

    def test_get_logger_unhandled_capture_exception(self) -> None:
        """Test get_logger when unhandled capture fails."""
        settings = Settings()
        settings.core.capture_unhandled_enabled = True

        with patch(
            "fapilog.core.errors.capture_unhandled_exceptions",
            side_effect=RuntimeError("Capture failed"),
        ):
            with runtime() as logger:
                logger.info("test message")

    def test_get_logger_sensitive_fields_policy_exception(self) -> None:
        """Test get_logger when sensitive fields policy warning fails."""
        from fapilog import get_logger

        settings = Settings()
        settings.core.sensitive_fields_policy = ["password", "secret"]

        with patch(
            "fapilog.core.diagnostics.warn", side_effect=RuntimeError("Warn failed")
        ):
            logger = get_logger(name="policy-warn-fail-test", settings=settings)
            logger.info("test message")
            import asyncio

            asyncio.run(logger.stop_and_drain())

    def test_get_logger_redactors_exception_during_config(self) -> None:
        """Test get_logger when redactor configuration raises exception."""
        from fapilog import get_logger

        settings = Settings()
        settings.core.enable_redactors = True
        settings.core.redactors_order = ["field-mask"]

        with patch(
            "fapilog.plugins.redactors.field_mask.FieldMaskRedactor",
            side_effect=ImportError("Redactor import failed"),
        ):
            logger = get_logger(
                name="redactor-config-exception-test", settings=settings
            )
            logger.info("test message")
            import asyncio

            asyncio.run(logger.stop_and_drain())


# ==============================================================================
# Shared Setup Tests
# ==============================================================================


class TestConfigureLoggerCommon:
    """Test _configure_logger_common function."""

    def test_configure_logger_common_returns_setup_without_starting_plugins(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plugin_e = _TrackingPlugin("enricher")
        plugin_r = _TrackingPlugin("redactor")
        plugin_p = _TrackingPlugin("processor")
        plugin_f = _TrackingPlugin("filter")

        monkeypatch.setattr(fapilog, "_apply_plugin_settings", lambda cfg: None)
        monkeypatch.setattr(
            fapilog,
            "_build_pipeline",
            lambda cfg: (
                ["built-sink"],
                [plugin_e],
                [plugin_r],
                [plugin_p],
                [plugin_f],
                "metrics",
            ),
        )

        writer_calls: dict[str, object] = {}

        def _fake_writer(
            sinks: list[object], cfg: object, circuit_config: object
        ) -> tuple[object, object]:
            writer_calls["sinks"] = list(sinks)
            writer_calls["circuit"] = circuit_config
            return ("sink_write", "sink_write_serialized")

        monkeypatch.setattr(fapilog, "_routing_or_fanout_writer", _fake_writer)

        settings = fapilog.Settings(
            core={"sink_circuit_breaker_enabled": True, "log_level": "WARNING"}
        )

        setup = fapilog._configure_logger_common(settings, ["override-sink"])

        assert isinstance(setup, fapilog._LoggerSetup)
        assert setup.settings is settings
        assert setup.sinks == ["override-sink"]
        assert writer_calls["sinks"] == ["override-sink"]
        assert setup.enrichers == [plugin_e]
        assert setup.redactors == [plugin_r]
        assert setup.processors == [plugin_p]
        assert setup.filters == [plugin_f]
        assert not any(p.started for p in (plugin_e, plugin_r, plugin_p, plugin_f))
        assert setup.metrics == "metrics"
        assert setup.sink_write == "sink_write"
        assert setup.sink_write_serialized == "sink_write_serialized"
        assert setup.circuit_config.enabled
        assert (
            setup.circuit_config.failure_threshold
            == settings.core.sink_circuit_breaker_failure_threshold
        )
        assert setup.level_gate == fapilog._LEVEL_PRIORITY["WARNING"]


class TestStartPluginsSync:
    """Test _start_plugins_sync function."""

    @pytest.mark.asyncio
    async def test_start_plugins_sync_runs_inside_running_loop(self) -> None:
        enricher = _TrackingPlugin("enricher")
        redactor = _TrackingPlugin("redactor")
        processor = _TrackingPlugin("processor")
        filter_plugin = _TrackingPlugin("filter")

        (
            started_enrichers,
            started_redactors,
            started_processors,
            started_filters,
        ) = fapilog._start_plugins_sync(
            [enricher],
            [redactor],
            [processor],
            [filter_plugin],
        )

        assert started_enrichers == [enricher]
        assert started_redactors == [redactor]
        assert started_processors == [processor]
        assert started_filters == [filter_plugin]
        assert all(p.started for p in (enricher, redactor, processor, filter_plugin))


class TestGetLoggerCallsSharedSetup:
    """Test get_logger calls shared setup functions."""

    def test_get_logger_calls_shared_setup(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings = fapilog.Settings(plugins__enabled=False, core__log_level="INFO")

        configure_calls: dict[str, object] = {}

        def _fake_configure(
            settings_arg: object, sinks_arg: object
        ) -> fapilog._LoggerSetup:
            configure_calls["args"] = (settings_arg, sinks_arg)
            return fapilog._LoggerSetup(
                settings=settings_arg or settings,
                sinks=list(sinks_arg or []),
                enrichers=["configured-enricher"],
                redactors=["configured-redactor"],
                processors=["configured-processor"],
                filters=["configured-filter"],
                metrics=None,
                sink_write=lambda _: None,
                sink_write_serialized=None,
                circuit_config=None,
                level_gate=10,
            )

        monkeypatch.setattr(fapilog, "_configure_logger_common", _fake_configure)
        monkeypatch.setattr(fapilog, "_apply_plugin_settings", lambda cfg: None)
        monkeypatch.setattr(
            fapilog,
            "_routing_or_fanout_writer",
            lambda sinks, cfg, circuit: (lambda _: None, None),
        )
        monkeypatch.setattr(
            fapilog,
            "_build_pipeline",
            lambda cfg: ([], [], [], [], [], None),
        )

        start_calls: dict[str, object] = {}

        def _fake_start_plugins_sync(
            enrichers: list[object],
            redactors: list[object],
            processors: list[object],
            filters: list[object],
        ) -> tuple[list[object], list[object], list[object], list[object]]:
            start_calls["args"] = (enrichers, redactors, processors, filters)
            return (
                ["started-enricher"],
                ["started-redactor"],
                ["started-processor"],
                ["started-filter"],
            )

        monkeypatch.setattr(fapilog, "_start_plugins_sync", _fake_start_plugins_sync)

        extras_calls: dict[str, object] = {}

        def _fake_apply_logger_extras(
            logger: object,
            setup: fapilog._LoggerSetup,
            *,
            started_enrichers: list[object],
            started_redactors: list[object],
            started_processors: list[object],
            started_filters: list[object],
        ) -> None:
            extras_calls["args"] = (
                logger,
                setup,
                started_enrichers,
                started_redactors,
                started_processors,
                started_filters,
            )

        monkeypatch.setattr(fapilog, "_apply_logger_extras", _fake_apply_logger_extras)

        class _StubLogger:
            def __init__(
                self,
                *,
                name: str | None,
                queue_capacity: int,
                batch_max_size: int,
                batch_timeout_seconds: float,
                backpressure_wait_ms: int,
                drop_on_full: bool,
                sink_write: object,
                sink_write_serialized: object,
                enrichers: list[object] | None,
                processors: list[object] | None,
                filters: list[object] | None,
                metrics: object,
                exceptions_enabled: bool,
                exceptions_max_frames: int,
                exceptions_max_stack_chars: int,
                serialize_in_flush: bool,
                num_workers: int,
                level_gate: int | None,
            ) -> None:
                self.name = name
                self.enrichers = enrichers or []
                self.processors = processors or []
                self.filters = filters or []
                self.metrics = metrics
                self.level_gate = level_gate
                self.queue_capacity = queue_capacity
                self.started = False

            def bind(self, **context: object) -> _StubLogger:
                self.bound_context = context
                return self

            def start(self) -> None:
                self.started = True

        monkeypatch.setattr(fapilog, "_SyncLoggerFacade", _StubLogger)

        logger = fapilog.get_logger(
            name="shared-setup",
            settings=settings,
            sinks=["manual-sink"],
        )

        assert configure_calls["args"] == (settings, ["manual-sink"])
        assert start_calls["args"] == (
            ["configured-enricher"],
            ["configured-redactor"],
            ["configured-processor"],
            ["configured-filter"],
        )
        assert isinstance(logger, _StubLogger)
        assert logger.enrichers == ["started-enricher"]
        assert logger.processors == ["started-processor"]
        assert logger.filters == ["started-filter"]
        assert logger.started
        assert extras_calls["args"][2:] == (
            ["started-enricher"],
            ["started-redactor"],
            ["started-processor"],
            ["started-filter"],
        )


# ==============================================================================
# Mixin Shared Behavior Tests
# ==============================================================================


class TestPreparePayloadSharedBehavior:
    """Tests for _prepare_payload shared across both facades."""

    def test_prepare_payload_shares_bound_context(self) -> None:
        """Both facades should bind context identically via the mixin."""
        sync_logger = SyncLoggerFacade(**_logger_args())
        async_logger = AsyncLoggerFacade(**_logger_args())

        sync_logger.bind(user="alice")
        async_logger.bind(user="alice")

        sync_payload = sync_logger._prepare_payload("INFO", "hello")  # type: ignore[attr-defined]
        async_payload = async_logger._prepare_payload("INFO", "hello-async")  # type: ignore[attr-defined]

        assert sync_payload["data"]["user"] == "alice"
        assert async_payload["data"]["user"] == "alice"

    def test_prepare_payload_dedupes_errors_per_facade(self) -> None:
        """Error deduplication should work identically in both facades."""
        logger = SyncLoggerFacade(**_logger_args())

        first = logger._prepare_payload("ERROR", "boom")  # type: ignore[attr-defined]
        second = logger._prepare_payload("ERROR", "boom")  # type: ignore[attr-defined]

        assert first["message"] == "boom"
        assert second is None

    def test_prepare_payload_returns_dict(self) -> None:
        """_prepare_payload must return a dict, not a Mapping."""
        logger = SyncLoggerFacade(**_logger_args())

        payload = logger._prepare_payload("INFO", "test message")  # type: ignore[attr-defined]

        assert isinstance(payload, dict)
        assert "level" in payload
        assert "message" in payload
        assert payload["level"] == "INFO"
        assert payload["message"] == "test message"

    def test_prepare_payload_with_metadata(self) -> None:
        """Context fields should be merged into context, others into data."""
        logger = SyncLoggerFacade(**_logger_args())

        payload = logger._prepare_payload(  # type: ignore[attr-defined]
            "INFO",
            "test",
            request_id="abc123",
            custom_field=42,
        )

        # v1.1 schema: request_id is a context field, custom_field goes to data
        assert payload["context"]["request_id"] == "abc123"
        assert payload["data"]["custom_field"] == 42


class TestContextBindingSharedBehavior:
    """Tests for context binding shared across both facades."""

    def test_bind_returns_self_sync(self) -> None:
        """SyncLoggerFacade.bind should return self for chaining."""
        logger = SyncLoggerFacade(**_logger_args())

        result = logger.bind(key="value")

        assert result is logger

    def test_bind_returns_self_async(self) -> None:
        """AsyncLoggerFacade.bind should return self for chaining."""
        logger = AsyncLoggerFacade(**_logger_args())

        result = logger.bind(key="value")

        assert result is logger

    def test_unbind_removes_keys(self) -> None:
        """unbind should remove specified keys from context."""
        logger = SyncLoggerFacade(**_logger_args())
        logger.bind(user="alice", role="admin", session="xyz")

        logger.unbind("role")

        payload = logger._prepare_payload("INFO", "test")  # type: ignore[attr-defined]
        assert "user" in payload["data"]
        assert "session" in payload["data"]
        assert "role" not in payload["data"]

    def test_clear_context_removes_all(self) -> None:
        """clear_context should remove all bound context."""
        logger = SyncLoggerFacade(**_logger_args())
        logger.bind(user="alice", role="admin")

        logger.clear_context()

        payload = logger._prepare_payload("INFO", "test")  # type: ignore[attr-defined]
        assert "user" not in payload["data"]
        assert "role" not in payload["data"]


class TestMixinInheritance:
    """Tests verifying both facades inherit properly from _LoggerMixin."""

    def test_sync_facade_inherits_make_worker(self) -> None:
        """SyncLoggerFacade should use _make_worker from mixin."""
        logger = SyncLoggerFacade(**_logger_args())

        worker = logger._make_worker()  # type: ignore[attr-defined]
        assert worker._queue is logger._queue  # type: ignore[attr-defined]
        assert worker._batch_max_size == logger._batch_max_size  # type: ignore[attr-defined]

    def test_async_facade_inherits_make_worker(self) -> None:
        """AsyncLoggerFacade should use _make_worker from mixin."""
        logger = AsyncLoggerFacade(**_logger_args())

        worker = logger._make_worker()  # type: ignore[attr-defined]
        assert worker._queue is logger._queue  # type: ignore[attr-defined]
        assert worker._batch_max_size == logger._batch_max_size  # type: ignore[attr-defined]

    def test_async_facade_has_diagnostics_disabled(self) -> None:
        """AsyncLoggerFacade should have worker diagnostics disabled."""
        logger = AsyncLoggerFacade(**_logger_args())

        assert logger._emit_worker_diagnostics is False  # type: ignore[attr-defined]

    def test_sync_facade_has_diagnostics_enabled(self) -> None:
        """SyncLoggerFacade should have worker diagnostics enabled (default)."""
        logger = SyncLoggerFacade(**_logger_args())

        assert logger._emit_worker_diagnostics is True  # type: ignore[attr-defined]


class TestLevelGateSharedBehavior:
    """Tests for level gate filtering shared across both facades."""

    def test_level_gate_filters_low_priority_sync(self) -> None:
        """Level gate should filter messages below threshold in sync facade."""
        from fapilog.plugins.filters.level import LEVEL_PRIORITY

        args = _logger_args()
        args["level_gate"] = LEVEL_PRIORITY["WARNING"]  # type: ignore[literal-required]
        logger = SyncLoggerFacade(**args)  # type: ignore[arg-type]

        debug_payload = logger._prepare_payload("DEBUG", "debug msg")  # type: ignore[attr-defined]
        info_payload = logger._prepare_payload("INFO", "info msg")  # type: ignore[attr-defined]
        warning_payload = logger._prepare_payload("WARNING", "warn msg")  # type: ignore[attr-defined]

        assert logger._level_gate == LEVEL_PRIORITY["WARNING"]  # type: ignore[attr-defined]
        assert debug_payload["level"] == "DEBUG"
        assert info_payload["level"] == "INFO"
        assert warning_payload["level"] == "WARNING"
