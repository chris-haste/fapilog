from __future__ import annotations

import asyncio
import io
import sys

import pytest

from fapilog import get_logger
from fapilog.core.settings import Settings
from fapilog.metrics.metrics import MetricsCollector, plugin_timer


@pytest.mark.asyncio
async def test_disabled_metrics_noop_and_state() -> None:
    mc = MetricsCollector(enabled=False)
    # record_event_processed should update in-memory counter even if disabled
    await mc.record_event_processed()
    # plugin error counter should update in-memory state
    await mc.record_plugin_error(plugin_name="x")
    snap = await mc.snapshot()
    assert snap.events_processed == 1
    assert snap.plugin_errors == 1

    # No exceptions on other methods when disabled
    await mc.record_events_submitted(2)
    await mc.record_events_dropped(1)
    await mc.record_backpressure_wait(3)
    await mc.record_flush(batch_size=5, latency_seconds=0.01)
    await mc.set_queue_high_watermark(10)
    await mc.record_sink_error(sink="stdout", count=1)


@pytest.mark.asyncio
async def test_enabled_basic_counters_and_histograms() -> None:
    mc = MetricsCollector(enabled=True)
    # Events processed with latency
    await mc.record_event_processed(duration_seconds=0.002)
    # Submitted/dropped/backpressure
    await mc.record_events_submitted(3)
    await mc.record_events_dropped(1)
    await mc.record_backpressure_wait(2)
    # Flush/batch size + queue gauge + sink error
    await mc.record_flush(batch_size=7, latency_seconds=0.004)
    await mc.set_queue_high_watermark(42)
    await mc.record_sink_error(sink="stdout", count=1)

    reg = mc.registry
    assert reg is not None
    # Validate counters incremented
    assert reg.get_sample_value("fapilog_events_processed_total") == 1.0
    assert reg.get_sample_value("fapilog_events_submitted_total") == 3.0
    assert reg.get_sample_value("fapilog_events_dropped_total") == 1.0
    assert reg.get_sample_value("fapilog_backpressure_waits_total") == 2.0
    # Histograms expose _count sample
    val_a = reg.get_sample_value("fapilog_event_process_seconds_count")
    assert val_a is not None
    val_b = reg.get_sample_value("fapilog_batch_size_count")
    assert val_b is not None
    val_c = reg.get_sample_value("fapilog_flush_seconds_count")
    assert val_c is not None
    # Gauge value
    assert reg.get_sample_value("fapilog_queue_high_watermark") == 42.0
    # Labeled sink error counter
    val = reg.get_sample_value(
        "fapilog_sink_errors_total",
        {"sink": "stdout"},
    )
    assert val == 1.0


@pytest.mark.asyncio
async def test_plugin_timer_success_and_error() -> None:
    mc = MetricsCollector(enabled=True)
    # Success path
    async with plugin_timer(mc, "p1"):
        await asyncio.sleep(0)
    reg = mc.registry
    assert reg is not None
    count = reg.get_sample_value(
        "fapilog_plugin_exec_seconds_count",
        {"plugin": "p1"},
    )
    assert (count or 0.0) >= 1.0

    # Error path
    with pytest.raises(RuntimeError):
        async with plugin_timer(mc, "p2"):
            raise RuntimeError("boom")
    # plugin_errors_total should increment for p2
    err_count = reg.get_sample_value(
        "fapilog_plugin_errors_total",
        {"plugin": "p2"},
    )
    assert (err_count or 0.0) >= 1.0


def _capture_stdout_setup():
    buf = io.BytesIO()
    orig = sys.stdout
    # Redirect stdout to capture JSON lines from sink
    sys.stdout = io.TextIOWrapper(
        buf,
        encoding="utf-8",
    )
    return buf, orig


def test_metrics_guardrails_enabled_vs_disabled_guardrails() -> None:
    # Disabled metrics: no exceptions on enqueue/flush
    buf, orig = _capture_stdout_setup()
    try:
        s = Settings()
        s.core.enable_metrics = False
        logger = get_logger("mtest-disabled", settings=s)
        for _ in range(5):
            logger.info("x")
        import time

        time.sleep(0.1)
        import asyncio

        asyncio.run(logger.stop_and_drain())
        sys.stdout.flush()
        lines = buf.getvalue().decode("utf-8").strip().splitlines()
        assert len(lines) >= 1  # At least some lines present; no exceptions
    finally:
        sys.stdout = orig  # type: ignore[assignment]

    # Enabled metrics: ensure flush latency histogram can be
    # updated within worker
    buf2, orig2 = _capture_stdout_setup()
    try:
        s2 = Settings()
        s2.core.enable_metrics = True
        logger2 = get_logger("mtest-enabled", settings=s2)
        for _ in range(10):
            logger2.info("y")
        import time

        time.sleep(0.2)
        import asyncio

        asyncio.run(logger2.stop_and_drain())
        sys.stdout.flush()
        text2 = buf2.getvalue().decode("utf-8").strip()
        lines2 = text2.splitlines()
        assert len(lines2) >= 1
    finally:
        sys.stdout = orig2  # type: ignore[assignment]
