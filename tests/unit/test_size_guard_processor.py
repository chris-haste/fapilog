from __future__ import annotations

import json
from typing import Iterable

import pytest

from fapilog import Settings
from fapilog.core import diagnostics
from fapilog.core.concurrency import NonBlockingRingQueue
from fapilog.core.events import LogEvent
from fapilog.core.worker import LoggerWorker, strict_envelope_mode_enabled
from fapilog.metrics.metrics import MetricsCollector
from fapilog.plugins import loader
from fapilog.plugins.processors.size_guard import SizeGuardConfig, SizeGuardProcessor


@pytest.fixture()
def capture_diagnostics(monkeypatch):
    diagnostics._reset_for_tests()
    monkeypatch.setenv("FAPILOG_CORE__INTERNAL_LOGGING_ENABLED", "true")
    captured: list[dict] = []
    original = diagnostics._writer
    diagnostics.set_writer_for_tests(captured.append)
    yield captured
    diagnostics.set_writer_for_tests(original)


@pytest.fixture()
def small_payload() -> memoryview:
    return memoryview(json.dumps({"level": "INFO", "message": "hello"}).encode())


@pytest.fixture()
def large_payload() -> memoryview:
    payload = {
        "level": "INFO",
        "timestamp": "2024-01-01T00:00:00Z",
        "logger": "demo",
        "message": "x" * 2048,
        "metadata": {"hint": "keep", "extra": "y" * 1024},
    }
    return memoryview(json.dumps(payload).encode())


def _make_worker(
    *,
    processors: Iterable[SizeGuardProcessor],
    sink_write_serialized,
    sink_write,
) -> LoggerWorker:
    return LoggerWorker(
        queue=NonBlockingRingQueue(capacity=4),
        batch_max_size=4,
        batch_timeout_seconds=0.01,
        sink_write=sink_write,
        sink_write_serialized=sink_write_serialized,
        filters_getter=lambda: [],
        enrichers_getter=lambda: [],
        redactors_getter=lambda: [],
        processors_getter=lambda: list(processors),
        metrics=None,
        serialize_in_flush=True,
        strict_envelope_mode_provider=strict_envelope_mode_enabled,
        stop_flag=lambda: False,
        drained_event=None,
        flush_event=None,
        flush_done_event=None,
        emit_filter_diagnostics=False,
        emit_enricher_diagnostics=False,
        emit_redactor_diagnostics=False,
        emit_processor_diagnostics=True,
        counters={"processed": 0, "dropped": 0},
    )


@pytest.mark.asyncio
async def test_small_payload_passes_through(small_payload: memoryview) -> None:
    proc = SizeGuardProcessor(config=SizeGuardConfig(max_bytes=512))

    out = await proc.process(small_payload)

    assert bytes(out) == bytes(small_payload)


@pytest.mark.asyncio
async def test_truncate_marks_payload_and_trims_message(
    large_payload: memoryview,
) -> None:
    proc = SizeGuardProcessor(config=SizeGuardConfig(max_bytes=300))

    result = await proc.process(large_payload)
    data = json.loads(bytes(result))

    assert data["_truncated"] is True
    assert data["_original_size"] == len(large_payload)
    assert "[truncated]" in data["message"]
    assert len(bytes(result)) <= proc._max_bytes  # noqa: SLF001


@pytest.mark.asyncio
async def test_drop_action_replaces_payload(large_payload: memoryview) -> None:
    proc = SizeGuardProcessor(config=SizeGuardConfig(max_bytes=200, action="drop"))

    result = await proc.process(large_payload)
    data = json.loads(bytes(result))

    assert data["_dropped"] is True
    assert data["_original_size"] == len(large_payload)
    assert data["_max_bytes"] == proc._max_bytes  # noqa: SLF001


@pytest.mark.asyncio
async def test_warn_action_emits_diagnostic(
    large_payload: memoryview, capture_diagnostics: list[dict]
) -> None:
    proc = SizeGuardProcessor(config=SizeGuardConfig(max_bytes=200, action="warn"))

    result = await proc.process(large_payload)

    assert bytes(result) == bytes(large_payload)
    assert capture_diagnostics
    event = capture_diagnostics[-1]
    assert event["component"] == "processor"
    assert event["message"].startswith("size_guard")
    assert event["original_size"] == len(large_payload)
    assert event["max_bytes"] == proc._max_bytes  # noqa: SLF001


@pytest.mark.asyncio
async def test_preserve_fields_survive_pruning() -> None:
    payload = {
        "level": "ERROR",
        "timestamp": "2024-02-02T02:02:02Z",
        "logger": "svc",
        "message": "y" * 4096,
        "metadata": {"correlation_id": "cid-123", "debug": "z" * 4096},
    }
    view = memoryview(json.dumps(payload).encode())
    proc = SizeGuardProcessor(config=SizeGuardConfig(max_bytes=320))

    result = await proc.process(view)
    data = json.loads(bytes(result))

    assert data["level"] == "ERROR"
    assert data["timestamp"] == "2024-02-02T02:02:02Z"
    assert data["logger"] == "svc"
    assert data.get("_truncated") is True


@pytest.mark.asyncio
async def test_metrics_recorded_for_actions(large_payload: memoryview) -> None:
    metrics = MetricsCollector(enabled=True)
    trunc = SizeGuardProcessor(
        config=SizeGuardConfig(max_bytes=300),
        metrics=metrics,
    )
    drop = SizeGuardProcessor(
        config=SizeGuardConfig(max_bytes=200, action="drop"),
        metrics=metrics,
    )

    await trunc.process(large_payload)
    await drop.process(large_payload)

    reg = metrics.registry
    assert reg is not None
    assert reg.get_sample_value("processor_size_guard_truncated_total") == 1.0
    assert reg.get_sample_value("processor_size_guard_dropped_total") == 1.0


@pytest.mark.asyncio
async def test_health_check_invalid_threshold() -> None:
    proc = SizeGuardProcessor(config=SizeGuardConfig(max_bytes=0))

    assert await proc.health_check() is False


def test_loader_registration_supports_aliases() -> None:
    plugin = loader.load_plugin("fapilog.processors", "size_guard", {})
    assert isinstance(plugin, SizeGuardProcessor)

    plugin_alias = loader.load_plugin("fapilog.processors", "size-guard", {})
    assert isinstance(plugin_alias, SizeGuardProcessor)


@pytest.mark.asyncio
async def test_worker_pipeline_applies_size_guard() -> None:
    captured: list[bytes] = []

    async def sink_write_serialized(view: memoryview) -> None:
        captured.append(bytes(view))

    async def sink_write(entry: dict) -> None:
        captured.append(json.dumps(entry).encode())

    processor = SizeGuardProcessor(config=SizeGuardConfig(max_bytes=240))
    worker = _make_worker(
        processors=[processor],
        sink_write_serialized=sink_write_serialized,
        sink_write=sink_write,
    )

    batch = [LogEvent(level="INFO", message="a" * 1024).to_mapping()]

    await worker.flush_batch(batch)

    assert captured
    data = json.loads(captured[0])
    assert data.get("_truncated") is True


def test_settings_support_env_aliases(monkeypatch) -> None:
    monkeypatch.setenv("FAPILOG_CORE__PROCESSORS", '["size_guard"]')
    monkeypatch.setenv("FAPILOG_PROCESSOR_CONFIG__SIZE_GUARD__MAX_BYTES", "123")
    monkeypatch.setenv("FAPILOG_SIZE_GUARD__ACTION", "drop")

    settings = Settings()

    assert settings.processor_config.size_guard.max_bytes == 123
    assert settings.processor_config.size_guard.action == "drop"


# --- Edge case tests ---


@pytest.mark.asyncio
async def test_malformed_json_falls_back_to_drop_marker() -> None:
    """Non-JSON input should fall back to drop marker during truncation."""
    proc = SizeGuardProcessor(config=SizeGuardConfig(max_bytes=10))
    invalid_json = memoryview(b"this is not valid json at all and exceeds limit")

    result = await proc.process(invalid_json)
    data = json.loads(bytes(result))

    assert data["_dropped"] is True
    assert data["_reason"] == "payload_size_exceeded"
    assert data["_original_size"] == len(invalid_json)


@pytest.mark.asyncio
async def test_empty_payload_passes_through() -> None:
    """Empty payload should pass through unchanged."""
    proc = SizeGuardProcessor(config=SizeGuardConfig(max_bytes=100))
    empty = memoryview(b"")

    result = await proc.process(empty)

    assert bytes(result) == b""


@pytest.mark.asyncio
async def test_payload_exactly_at_limit_passes_through() -> None:
    """Payload exactly at max_bytes should pass through unchanged."""
    # Build a payload of exactly 100 bytes
    base = {"a": ""}
    base_len = len(json.dumps(base).encode())
    padding = "x" * (100 - base_len)
    payload = json.dumps({"a": padding}).encode()
    assert len(payload) == 100

    proc = SizeGuardProcessor(config=SizeGuardConfig(max_bytes=100))
    result = await proc.process(memoryview(payload))

    assert bytes(result) == payload


@pytest.mark.asyncio
async def test_payload_one_byte_over_limit_triggers_action() -> None:
    """Payload one byte over max_bytes should trigger the configured action."""
    base = {"a": ""}
    base_len = len(json.dumps(base).encode())
    padding = "x" * (101 - base_len)
    payload = json.dumps({"a": padding}).encode()
    assert len(payload) == 101

    proc = SizeGuardProcessor(config=SizeGuardConfig(max_bytes=100, action="drop"))
    result = await proc.process(memoryview(payload))
    data = json.loads(bytes(result))

    assert data["_dropped"] is True


@pytest.mark.asyncio
async def test_health_check_valid_config() -> None:
    """Health check returns True for valid configuration."""
    proc = SizeGuardProcessor(config=SizeGuardConfig(max_bytes=256000))

    assert await proc.health_check() is True


@pytest.mark.asyncio
async def test_negative_max_bytes_treated_as_invalid() -> None:
    """Negative max_bytes should be treated as invalid config."""
    proc = SizeGuardProcessor(config=SizeGuardConfig(max_bytes=-100))

    assert await proc.health_check() is False
    # Payloads should pass through when config is invalid
    payload = memoryview(b'{"test": "data"}')
    result = await proc.process(payload)
    assert bytes(result) == bytes(payload)


@pytest.mark.asyncio
async def test_truncation_preserves_json_validity_with_unicode() -> None:
    """Truncation should preserve valid JSON even with unicode characters."""
    payload = {
        "level": "INFO",
        "message": "日本語テスト" * 500,  # Unicode that might break mid-character
    }
    view = memoryview(json.dumps(payload, ensure_ascii=False).encode())
    proc = SizeGuardProcessor(config=SizeGuardConfig(max_bytes=200))

    result = await proc.process(view)

    # Must be valid JSON
    data = json.loads(bytes(result))
    assert data.get("_truncated") is True or data.get("_dropped") is True


@pytest.mark.asyncio
async def test_heavily_truncated_marker_when_all_strategies_fail() -> None:
    """When all truncation strategies fail, should mark as heavily truncated."""
    # Create payload where even message truncation isn't enough
    payload = {
        "level": "ERROR",
        "timestamp": "2024-01-01T00:00:00Z",
        "logger": "test",
        "message": "short",
        "huge_field": "x" * 10000,
    }
    view = memoryview(json.dumps(payload).encode())
    # Very small limit forces aggressive truncation
    proc = SizeGuardProcessor(config=SizeGuardConfig(max_bytes=150))

    result = await proc.process(view)
    data = json.loads(bytes(result))

    # Should preserve critical fields
    assert data["level"] == "ERROR"
    assert data["timestamp"] == "2024-01-01T00:00:00Z"
    assert data["logger"] == "test"
    assert data.get("_truncated") is True
    # Large field should be removed
    assert "huge_field" not in data


@pytest.mark.asyncio
async def test_custom_preserve_fields() -> None:
    """Custom preserve_fields should be respected during truncation."""
    payload = {
        "level": "INFO",
        "custom_id": "keep-me",
        "message": "x" * 5000,
    }
    view = memoryview(json.dumps(payload).encode())
    proc = SizeGuardProcessor(
        config=SizeGuardConfig(
            max_bytes=200,
            preserve_fields=["level", "custom_id"],
        )
    )

    result = await proc.process(view)
    data = json.loads(bytes(result))

    assert data["level"] == "INFO"
    assert data["custom_id"] == "keep-me"
    assert data.get("_truncated") is True
