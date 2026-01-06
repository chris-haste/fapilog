from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from fapilog import Settings


class FakeSink:
    def __init__(self, name: str = "sink") -> None:
        self.name = name
        self.write = AsyncMock()
        self.write_serialized = AsyncMock()
        self.start = AsyncMock()
        self._started = False


def _build_writer(*, sinks: list[Any], routing_cfg: Any, parallel: bool = False):
    from fapilog.core.routing import build_routing_writer

    return build_routing_writer(
        sinks,
        routing_cfg,
        parallel=parallel,
        circuit_config=None,
    )


@pytest.mark.asyncio
async def test_routing_writer_routes_by_level() -> None:
    error = FakeSink("error")
    info = FakeSink("info")
    cfg = SimpleNamespace(
        rules=[
            SimpleNamespace(levels=["ERROR"], sinks=["error"]),
            SimpleNamespace(levels=["INFO"], sinks=["info"]),
        ],
        fallback_sinks=[],
        overlap=True,
    )
    sink_write, _ = _build_writer(sinks=[error, info], routing_cfg=cfg)

    await sink_write({"level": "ERROR", "message": "boom"})

    error.write.assert_awaited_once()
    info.write.assert_not_awaited()


@pytest.mark.asyncio
async def test_routing_writer_overlap_sends_to_all_matches() -> None:
    sink1 = FakeSink("s1")
    sink2 = FakeSink("s2")
    cfg = SimpleNamespace(
        rules=[
            SimpleNamespace(levels=["ERROR"], sinks=["s1"]),
            SimpleNamespace(levels=["ERROR"], sinks=["s2"]),
        ],
        fallback_sinks=[],
        overlap=True,
    )
    sink_write, _ = _build_writer(sinks=[sink1, sink2], routing_cfg=cfg)

    await sink_write({"level": "ERROR", "message": "boom"})

    sink1.write.assert_awaited_once()
    sink2.write.assert_awaited_once()


@pytest.mark.asyncio
async def test_routing_writer_first_match_when_overlap_disabled() -> None:
    sink1 = FakeSink("s1")
    sink2 = FakeSink("s2")
    cfg = SimpleNamespace(
        rules=[
            SimpleNamespace(levels=["ERROR"], sinks=["s1"]),
            SimpleNamespace(levels=["ERROR"], sinks=["s2"]),
        ],
        fallback_sinks=[],
        overlap=False,
    )
    sink_write, _ = _build_writer(sinks=[sink1, sink2], routing_cfg=cfg)

    await sink_write({"level": "ERROR", "message": "boom"})

    sink1.write.assert_awaited_once()
    sink2.write.assert_not_awaited()


@pytest.mark.asyncio
async def test_routing_writer_fallback_when_no_match() -> None:
    fallback = FakeSink("fallback")
    cfg = SimpleNamespace(
        rules=[
            SimpleNamespace(levels=["ERROR"], sinks=["missing"]),
        ],
        fallback_sinks=["fallback"],
        overlap=True,
    )
    sink_write, _ = _build_writer(sinks=[fallback], routing_cfg=cfg)

    await sink_write({"level": "INFO", "message": "info"})

    fallback.write.assert_awaited_once()


@pytest.mark.asyncio
async def test_routing_writer_parallel_paths() -> None:
    sink1 = FakeSink("s1")
    sink2 = FakeSink("s2")
    cfg = SimpleNamespace(
        rules=[SimpleNamespace(levels=["ERROR"], sinks=["s1", "s2"])],
        fallback_sinks=[],
        overlap=True,
    )
    sink_write, _ = _build_writer(sinks=[sink1, sink2], routing_cfg=cfg, parallel=True)

    await sink_write({"level": "ERROR", "message": "boom"})

    assert sink1.write.await_count == 1
    assert sink2.write.await_count == 1


def test_sink_routing_env_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    rules = [
        {"levels": ["ERROR", "CRITICAL"], "sinks": ["postgres", "webhook"]},
        {"levels": ["DEBUG", "INFO"], "sinks": ["stdout_json"]},
    ]
    monkeypatch.setenv("FAPILOG_SINK_ROUTING__ENABLED", "true")
    monkeypatch.setenv("FAPILOG_SINK_ROUTING__OVERLAP", "false")
    monkeypatch.setenv("FAPILOG_SINK_ROUTING__RULES", json.dumps(rules))
    monkeypatch.setenv("FAPILOG_SINK_ROUTING__FALLBACK_SINKS", "rotating_file")

    settings = Settings()
    routing = settings.sink_routing

    assert routing.enabled is True
    assert routing.overlap is False
    assert len(routing.rules) == 2
    assert routing.rules[0].levels == ["ERROR", "CRITICAL"]
    assert routing.fallback_sinks == ["rotating_file"]


@pytest.mark.asyncio
async def test_routing_sink_plugin_routes_to_child(monkeypatch: pytest.MonkeyPatch):
    from fapilog.plugins.sinks.routing import RoutingSink, RoutingSinkConfig
    from fapilog.testing.mocks import MockSink

    child = MockSink()

    def fake_load_plugin(group: str, name: str, config: Any):
        assert group == "fapilog.sinks"
        return child

    monkeypatch.setattr(
        "fapilog.plugins.sinks.routing.loader.load_plugin", fake_load_plugin
    )

    sink = RoutingSink(
        RoutingSinkConfig(
            routes={"ERROR": ["mock"], "*": ["mock"]},
            parallel=True,
        )
    )
    await sink.start()

    await sink.write({"level": "ERROR", "message": "boom"})
    await sink.stop()

    assert child.write_count == 1
    assert child.stop_called is True


# --- P1: Test for update_rules() dynamic rule updates (AC4) ---


@pytest.mark.asyncio
async def test_update_rules_changes_routing() -> None:
    """Verify that update_rules() allows hot-reloading routing rules."""
    from fapilog.core.routing import RoutingSinkWriter

    sink1 = FakeSink("s1")
    sink2 = FakeSink("s2")

    writer = RoutingSinkWriter(
        sinks=[sink1, sink2],
        rules=[({"ERROR"}, ["s1"])],
        fallback_sink_names=[],
        overlap=True,
    )

    # Initial routing: ERROR -> s1
    await writer.write({"level": "ERROR", "message": "first"})
    assert sink1.write.await_count == 1
    assert sink2.write.await_count == 0

    # Hot-reload: ERROR -> s2
    writer.update_rules([({"ERROR"}, ["s2"])], [])
    sink1.write.reset_mock()
    sink2.write.reset_mock()

    await writer.write({"level": "ERROR", "message": "second"})
    assert sink1.write.await_count == 0
    assert sink2.write.await_count == 1


@pytest.mark.asyncio
async def test_update_rules_with_fallback() -> None:
    """Verify update_rules() properly updates fallback sinks."""
    from fapilog.core.routing import RoutingSinkWriter

    sink1 = FakeSink("s1")
    fallback = FakeSink("fallback")

    writer = RoutingSinkWriter(
        sinks=[sink1, fallback],
        rules=[({"ERROR"}, ["s1"])],
        fallback_sink_names=[],
        overlap=True,
    )

    # INFO has no rule and no fallback -> dropped
    await writer.write({"level": "INFO", "message": "dropped"})
    assert fallback.write.await_count == 0

    # Update to add fallback
    writer.update_rules([({"ERROR"}, ["s1"])], ["fallback"])
    await writer.write({"level": "INFO", "message": "caught"})
    assert fallback.write.await_count == 1


# --- P1: Performance benchmark for <1μs routing overhead (AC6) ---


def test_routing_lookup_performance(benchmark: Any) -> None:
    """Benchmark: routing lookup should be O(1) and <1μs."""
    from fapilog.core.routing import RoutingSinkWriter

    sinks = [FakeSink(f"s{i}") for i in range(5)]
    writer = RoutingSinkWriter(
        sinks=sinks,
        rules=[
            ({"ERROR", "CRITICAL"}, ["s0", "s1"]),
            ({"INFO", "WARNING"}, ["s2", "s3"]),
            ({"DEBUG"}, ["s4"]),
        ],
        fallback_sink_names=[],
        overlap=True,
    )

    result = benchmark(writer.get_sinks_for_level, "ERROR")
    assert len(result) == 2
    # pytest-benchmark will report stats; we assert sub-microsecond in CI


# --- P1: Integration test with real sinks (AC8) ---


@pytest.mark.asyncio
async def test_integration_with_real_stdout_json_sink(capsys: Any) -> None:
    """Integration test using real StdoutJsonSink (no mocking)."""
    from fapilog.core.routing import RoutingSinkWriter
    from fapilog.plugins.sinks.stdout_json import StdoutJsonSink

    stdout_sink = StdoutJsonSink()

    writer = RoutingSinkWriter(
        sinks=[stdout_sink],
        rules=[({"INFO"}, ["stdout_json"])],
        fallback_sink_names=[],
        overlap=True,
    )

    await writer.write({"level": "INFO", "message": "integration test"})

    captured = capsys.readouterr()
    assert "integration test" in captured.out
    assert "INFO" in captured.out


@pytest.mark.asyncio
async def test_integration_multi_sink_routing(capsys: Any) -> None:
    """Integration test: route different levels to different real sinks."""
    from fapilog.core.routing import RoutingSinkWriter
    from fapilog.plugins.sinks.stdout_json import StdoutJsonSink

    # Two distinct stdout sinks (same type, but different instances)
    info_sink = StdoutJsonSink()
    info_sink.name = "info_sink"
    error_sink = StdoutJsonSink()
    error_sink.name = "error_sink"

    writer = RoutingSinkWriter(
        sinks=[info_sink, error_sink],
        rules=[
            ({"INFO"}, ["info_sink"]),
            ({"ERROR"}, ["error_sink"]),
        ],
        fallback_sink_names=[],
        overlap=True,
    )

    await writer.write({"level": "INFO", "message": "info message"})
    await writer.write({"level": "ERROR", "message": "error message"})

    captured = capsys.readouterr()
    # Both messages should appear (both sinks write to same stdout)
    assert "info message" in captured.out
    assert "error message" in captured.out


# --- Missing: Test for write_serialized path ---


@pytest.mark.asyncio
async def test_routing_writer_write_serialized() -> None:
    """Test write_serialized routes correctly based on level."""
    error_sink = FakeSink("error")
    info_sink = FakeSink("info")

    # Create a mock serialized view with level attribute
    class MockView:
        level = "ERROR"
        data = b'{"level": "ERROR", "message": "test"}'

    _, sink_write_serialized = _build_writer(
        sinks=[error_sink, info_sink],
        routing_cfg=SimpleNamespace(
            rules=[
                SimpleNamespace(levels=["ERROR"], sinks=["error"]),
                SimpleNamespace(levels=["INFO"], sinks=["info"]),
            ],
            fallback_sinks=[],
            overlap=True,
        ),
    )

    view = MockView()
    await sink_write_serialized(view)

    error_sink.write_serialized.assert_awaited_once()
    info_sink.write_serialized.assert_not_awaited()


@pytest.mark.asyncio
async def test_routing_drops_when_no_match_and_no_fallback() -> None:
    """Verify events are silently dropped when no rule matches and no fallback."""
    from fapilog.core.routing import RoutingSinkWriter

    error_sink = FakeSink("error")

    writer = RoutingSinkWriter(
        sinks=[error_sink],
        rules=[({"ERROR"}, ["error"])],
        fallback_sink_names=[],
        overlap=True,
    )

    # INFO has no matching rule and no fallback -> should not raise
    await writer.write({"level": "INFO", "message": "dropped"})
    error_sink.write.assert_not_awaited()


@pytest.mark.asyncio
async def test_routing_level_case_insensitive() -> None:
    """Verify level matching is case-insensitive."""
    from fapilog.core.routing import RoutingSinkWriter

    sink = FakeSink("sink")

    writer = RoutingSinkWriter(
        sinks=[sink],
        rules=[({"ERROR"}, ["sink"])],
        fallback_sink_names=[],
        overlap=True,
    )

    # Various case combinations
    await writer.write({"level": "error", "message": "lower"})
    await writer.write({"level": "Error", "message": "mixed"})
    await writer.write({"level": "ERROR", "message": "upper"})

    assert sink.write.await_count == 3


@pytest.mark.asyncio
async def test_routing_handles_missing_level_field() -> None:
    """Verify events without level field default to INFO."""
    from fapilog.core.routing import RoutingSinkWriter

    info_sink = FakeSink("info")
    fallback_sink = FakeSink("fallback")

    writer = RoutingSinkWriter(
        sinks=[info_sink, fallback_sink],
        rules=[({"INFO"}, ["info"])],
        fallback_sink_names=["fallback"],
        overlap=True,
    )

    # No level field -> defaults to INFO
    await writer.write({"message": "no level"})
    info_sink.write.assert_awaited_once()
    fallback_sink.write.assert_not_awaited()


@pytest.mark.asyncio
async def test_routing_wildcard_in_rules() -> None:
    """Verify '*' in rules acts as fallback."""
    from fapilog.core.routing import RoutingSinkWriter

    error_sink = FakeSink("error")
    wildcard_sink = FakeSink("wildcard")

    writer = RoutingSinkWriter(
        sinks=[error_sink, wildcard_sink],
        rules=[
            ({"ERROR"}, ["error"]),
            ({"*"}, ["wildcard"]),  # Wildcard rule
        ],
        fallback_sink_names=[],
        overlap=True,
    )

    # ERROR -> error sink
    await writer.write({"level": "ERROR", "message": "error"})
    error_sink.write.assert_awaited_once()

    # DEBUG -> wildcard (fallback via * rule)
    await writer.write({"level": "DEBUG", "message": "debug"})
    wildcard_sink.write.assert_awaited_once()
