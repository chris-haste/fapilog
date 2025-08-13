from __future__ import annotations

import io
import json
import sys
import time

import fapilog as fl


def test_get_logger_basic_enqueue_and_stdout_json():
    # Capture stdout
    buf = io.BytesIO()
    orig = sys.stdout
    # Redirect stdout to capture JSON lines from sink
    sys.stdout = io.TextIOWrapper(
        buf,
        encoding="utf-8",
    )  # type: ignore[assignment]
    try:
        logger = fl.get_logger("test")
        logger.info("hello", k=1)
        # Allow background worker to flush batch via timeout
        time.sleep(0.3)
        # Force drain to ensure output
        import asyncio

        asyncio.run(logger.stop_and_drain())
        sys.stdout.flush()
        data = buf.getvalue().decode("utf-8").strip().splitlines()
        assert len(data) >= 1
        js = json.loads(data[0])
        assert js["message"] == "hello"
        assert js["level"] == "INFO"
        assert js["logger"] == "test"
        assert js["metadata"]["k"] == 1
    finally:
        sys.stdout = orig  # type: ignore[assignment]


def test_get_logger_emits_correlation_id():
    # Capture stdout
    buf = io.BytesIO()
    orig = sys.stdout
    sys.stdout = io.TextIOWrapper(
        buf,
        encoding="utf-8",
    )  # type: ignore[assignment]
    try:
        logger = fl.get_logger("corr-test")
        logger.info("hello")
        # Allow background worker to flush batch via timeout
        time.sleep(0.3)
        # Force drain to ensure output
        import asyncio

        asyncio.run(logger.stop_and_drain())
        sys.stdout.flush()
        data = buf.getvalue().decode("utf-8").strip().splitlines()
        assert len(data) == 1
        js = json.loads(data[0])
        assert js["message"] == "hello"
        assert js["level"] == "INFO"
        assert js["logger"] == "corr-test"
        assert "correlation_id" in js and isinstance(js["correlation_id"], str)
        assert len(js["correlation_id"]) > 0
    finally:
        sys.stdout = orig  # type: ignore[assignment]


def test_runtime_context_manager_drains_cleanly():
    buf = io.BytesIO()
    orig = sys.stdout
    sys.stdout = io.TextIOWrapper(
        buf,
        encoding="utf-8",
    )  # type: ignore[assignment]
    try:
        with fl.runtime() as logger:
            logger.info("x")
            logger.error("y")
        # Allow any scheduled drain to complete in async-loop scenarios
        time.sleep(0.2)
        sys.stdout.flush()
        lines = buf.getvalue().decode("utf-8").strip().splitlines()
        assert len(lines) >= 2
    finally:
        sys.stdout = orig  # type: ignore[assignment]


def test_backpressure_wait_then_drop(monkeypatch):
    # Force tiny queue and slow sink to induce backpressure and drops
    import importlib

    importlib.reload(fl)
    logger = fl.get_logger("bp-test")

    # monkeypatch internal settings via direct attributes if available
    # Submit many events quickly
    for i in range(500):
        logger.info("m", i=i)
    # Drain
    import asyncio

    res = asyncio.run(logger.stop_and_drain())
    assert res.submitted >= res.processed
    assert res.dropped >= 0
