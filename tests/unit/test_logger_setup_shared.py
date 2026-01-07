from __future__ import annotations

import pytest

import fapilog


class _TrackingPlugin:
    def __init__(self, name: str) -> None:
        self.name = name
        self.started = False

    async def start(self) -> None:
        self.started = True


def test_configure_logger_common_returns_setup_without_starting_plugins(
    monkeypatch: pytest.MonkeyPatch,
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
    assert setup.circuit_config is not None
    assert setup.circuit_config.enabled
    assert (
        setup.circuit_config.failure_threshold
        == settings.core.sink_circuit_breaker_failure_threshold
    )
    assert setup.level_gate == fapilog._LEVEL_PRIORITY["WARNING"]


@pytest.mark.asyncio
async def test_start_plugins_sync_runs_inside_running_loop() -> None:
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


def test_get_logger_calls_shared_setup(monkeypatch: pytest.MonkeyPatch) -> None:
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
