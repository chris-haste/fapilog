"""
Test fast path serialization behavior.

Scope:
- Fast path write_serialized success
- Strict envelope mode drop behavior
- Fast path fallback on error
- Stdout sink fast path wiring

Does NOT cover:
- General flush behavior (see test_logger_pipeline.py)
- Serialization error recovery (see test_logger_pipeline.py)
"""

from __future__ import annotations

import asyncio
import io
import sys
from typing import Any
from unittest.mock import patch

import pytest

from fapilog import get_logger
from fapilog.core.logger import SyncLoggerFacade
from fapilog.core.serialization import serialize_mapping_to_json_bytes


class TestFastPathSuccess:
    """Tests for successful fast path serialization."""

    @pytest.mark.asyncio
    async def test_fastpath_uses_write_serialized_success_bytes_match(self) -> None:
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

        assert observed["calls"] == 1
        # Validate serialized payload structure without depending on exact bytes
        import json as _json

        data = _json.loads(bytes(observed["data"]).decode("utf-8"))
        assert isinstance(data, dict)
        if "schema_version" in data:
            assert data.get("schema_version") == "1.1"  # v1.1 schema
            log = data.get("log", {})
            assert log.get("message") == "hello"
            assert log.get("level") == "INFO"
        else:
            # Best-effort mapping serialization fallback
            assert data.get("message") == "hello"
            assert data.get("level") == "INFO"
            assert data.get("logger") == "t"


class TestFastPathStrictMode:
    """Tests for strict envelope mode behavior."""

    @pytest.mark.asyncio
    async def test_fastpath_strict_envelope_error_drops_entry(self) -> None:
        """In strict mode, events with non-serializable data are dropped."""
        calls = {"serialized": 0, "dict": 0}

        class NonSerializable:
            pass

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
            # v1.1: valid events serialize successfully, only non-serializable fails
            logger.info("bad-event", payload=NonSerializable())
            await asyncio.sleep(0.05)
            await logger.stop_and_drain()

        # In strict mode, events that fail serialization are dropped (no fallback)
        assert calls["serialized"] == 0
        assert calls["dict"] == 0


class TestFastPathFallback:
    """Tests for fast path fallback behavior on errors."""

    @pytest.mark.asyncio
    async def test_fastpath_serialize_in_flush_falls_back_on_error(self) -> None:
        collected: list[dict[str, Any]] = []
        attempted: dict[str, int] = {"serialized_calls": 0}

        async def _sink_write(entry: dict[str, Any]) -> None:
            collected.append(dict(entry))

        async def _sink_write_serialized(_view: object) -> None:
            # Simulate a sink that declares fast path but fails at runtime
            attempted["serialized_calls"] += 1
            raise RuntimeError("boom")

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
        logger.info("m", i=1)
        # Allow timeout-based flush
        await asyncio.sleep(0.05)
        await logger.stop_and_drain()

        # Fast path attempted, but fell back to dict write
        assert attempted["serialized_calls"] == 1
        assert len(collected) == 1


class TestFastPathWiring:
    """Tests for fast path wiring in get_logger."""

    @pytest.mark.asyncio
    async def test_get_logger_sink_write_serialized_wrapper_writes_stdout(self) -> None:
        # get_logger() chooses stdout sink by default when no file env is set.
        logger = get_logger(name="t-fastpath")

        # Capture stdout bytes
        buf = io.BytesIO()
        orig_stdout = sys.stdout
        sys.stdout = io.TextIOWrapper(buf, encoding="utf-8")  # type: ignore[assignment]
        try:
            view = serialize_mapping_to_json_bytes({"a": 1})
            # Call the duck-typed wrapper wired by get_logger
            await logger._sink_write_serialized(view)  # type: ignore[attr-defined]
            sys.stdout.flush()
            text = buf.getvalue().decode("utf-8").strip()
            assert text == '{"a":1}'
        finally:
            sys.stdout = orig_stdout  # type: ignore[assignment]

        # Clean up logger to avoid background tasks lingering
        await logger.stop_and_drain()
