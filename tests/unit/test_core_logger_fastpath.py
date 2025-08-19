from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import pytest

from fapilog.core.logger import SyncLoggerFacade


@pytest.mark.asyncio
async def test_fastpath_uses_write_serialized_success_bytes_match() -> None:
    observed: dict[str, Any] = {"calls": 0, "data": b""}

    class TestSink:
        async def write(self, _entry: dict[str, Any]) -> None:  # pragma: no cover
            pass

        async def write_serialized(self, view: object) -> None:
            observed["calls"] += 1
            # view has .data bytes
            observed["data"] = view.data

    sink = TestSink()

    async def _sink_write(entry: dict[str, Any]) -> None:
        await sink.write(entry)

    async def _sink_write_serialized(view: object) -> None:
        await sink.write_serialized(view)

    logger = SyncLoggerFacade(
        name="t",
        queue_capacity=16,
        batch_max_size=8,
        batch_timeout_seconds=0.01,
        backpressure_wait_ms=1,
        drop_on_full=True,
        sink_write=_sink_write,
        sink_write_serialized=_sink_write_serialized,
        enrichers=[],
        metrics=None,
        serialize_in_flush=True,
    )
    logger.start()
    logger.info("hello", x=1)
    await asyncio.sleep(0.05)
    await logger.stop_and_drain()

    assert observed["calls"] >= 1
    # Validate serialized payload structure without depending on exact bytes
    import json as _json

    data = _json.loads(bytes(observed["data"]).decode("utf-8"))
    assert isinstance(data, dict)
    if "schema_version" in data:
        assert data.get("schema_version") == "1.0"
        log = data.get("log", {})
        assert log.get("message") == "hello"
        assert log.get("level") == "INFO"
    else:
        # Best-effort mapping serialization fallback
        assert data.get("message") == "hello"
        assert data.get("level") == "INFO"
        assert data.get("logger") == "t"


@pytest.mark.asyncio
async def test_fastpath_strict_envelope_error_drops_entry() -> None:
    calls = {"serialized": 0, "dict": 0}

    async def _sink_write(_entry: dict[str, Any]) -> None:
        calls["dict"] += 1

    async def _sink_write_serialized(_view: object) -> None:
        calls["serialized"] += 1

    # Force Settings().core.strict_envelope_mode = True so fast-path drops on error
    with patch("fapilog.core.settings.Settings") as MockSettings:
        cfg = MockSettings.return_value
        cfg.core.strict_envelope_mode = True

        logger = SyncLoggerFacade(
            name="t",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=_sink_write,
            sink_write_serialized=_sink_write_serialized,
            enrichers=[],
            metrics=None,
            serialize_in_flush=True,
        )
        logger.start()
        logger.info("hello")
        await asyncio.sleep(0.05)
        await logger.stop_and_drain()

    # In strict mode, envelope error should cause drop (no sink calls)
    assert calls["serialized"] == 0
    assert calls["dict"] == 0
