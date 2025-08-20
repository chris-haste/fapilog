"""Benchmarking utility for evaluating performance claims.

This script measures throughput, per-call latency, and memory usage for:
- fapilog (via get_logger) writing to a rotating file sink
- Python stdlib logging writing to a file

It produces evidence and a verdict for the following claims:
  - D001: "50x throughput improvement over traditional logging"
  - D002: "90% latency reduction with async-first design"
  - D003: "80% memory reduction with zero-copy operations"

Notes:
- Results are environment dependent; run multiple iterations for stability.
- Throughput here measures front-end log-call rate, not backend I/O flush time.
  We also ensure a flush/close after the run to avoid data loss.
- Memory is measured with tracemalloc peak during the test window.

Enterprise-focused tests (opt-in):
- Slow-sink non-blocking latency: compare app-side log-call latency when sink is slow
- Burst absorption with backpressure/drops: measure submitted/processed/dropped and tail latency
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import gc
import json
import logging
import os
import statistics
import tempfile
import time
from pathlib import Path
from typing import Callable


def _setup_stdlib_logger(file_path: Path) -> logging.Logger:
    logger = logging.getLogger("benchmark_stdlib")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(file_path, mode="w", encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def _setup_fapilog_logger(directory: Path, *, serialize_in_flush: bool | None = None):
    # Configure fapilog to write to rotating file sink in a temp directory
    # via environment variables that get_logger() reads.
    os.environ["FAPILOG_FILE__DIRECTORY"] = str(directory)
    # Keep metrics off to reduce overhead variability
    os.environ["FAPILOG_ENABLE_METRICS"] = "0"
    # Import lazily after env vars are set
    from fapilog import get_logger  # type: ignore

    # Fast-path and strict mode defaults for benchmarking
    os.environ.setdefault("FAPILOG_CORE__STRICT_ENVELOPE_MODE", "0")
    if serialize_in_flush is not None:
        os.environ["FAPILOG_CORE__SERIALIZE_IN_FLUSH"] = (
            "1" if serialize_in_flush else "0"
        )
    return get_logger(name="benchmark_fapilog")


def _generate_payload(size_bytes: int) -> dict[str, object]:
    # Repeat a small token to reach the desired size approximately
    base = {"user": "u123", "action": "test", "ok": True}
    filler = "x" * max(0, size_bytes - len(json.dumps(base)))
    return {**base, "payload": filler}


def _run_throughput(
    test_fn: Callable[[], None], iterations: int
) -> tuple[float, float]:
    start = time.perf_counter()
    for _ in range(iterations):
        test_fn()
    end = time.perf_counter()
    elapsed = end - start
    rate = iterations / elapsed if elapsed > 0 else float("inf")
    return elapsed, rate


def _run_latency(test_fn: Callable[[], None], iterations: int) -> dict[str, float]:
    samples = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        test_fn()
        t1 = time.perf_counter()
        samples.append((t1 - t0) * 1e6)  # microseconds
    samples.sort()
    median = statistics.median(samples)
    p95 = samples[int(len(samples) * 0.95) - 1] if samples else 0.0
    avg = statistics.fmean(samples) if samples else 0.0
    return {"avg_us": avg, "median_us": median, "p95_us": p95}


def _run_memory(test_fn: Callable[[], None], iterations: int) -> int:
    import tracemalloc

    gc.collect()
    tracemalloc.start()
    peak = 0
    for _ in range(iterations):
        test_fn()
        current, pk = tracemalloc.get_traced_memory()
        if pk > peak:
            peak = pk
    tracemalloc.stop()
    return peak  # bytes


def benchmark(
    iterations: int,
    latency_iterations: int,
    payload_size: int,
) -> dict[str, object]:
    results: dict[str, object] = {}
    with tempfile.TemporaryDirectory(prefix="fapilog_bench_") as tmpdir:
        tmp = Path(tmpdir)
        std_file = tmp / "stdlib.log"

        # stdlib logger setup
        std_logger = _setup_stdlib_logger(std_file)
        std_payload = _generate_payload(payload_size)
        std_message = json.dumps(std_payload, separators=(",", ":"))

        def std_call() -> None:
            std_logger.info(std_message)

        # fapilog logger setup (to its own rotating file directory)
        fapi_dir = tmp / "fapilog"
        fapi_dir.mkdir(parents=True, exist_ok=True)
        # Prepare two loggers: fastpath OFF and ON
        fapi_logger_off = _setup_fapilog_logger(fapi_dir, serialize_in_flush=False)
        fapi_logger_on = _setup_fapilog_logger(fapi_dir, serialize_in_flush=True)
        fapi_payload = _generate_payload(payload_size)

        def fapi_call_off() -> None:
            # fapilog will JSON-serialize dict payloads
            fapi_logger_off.info("bench", extra={"payload": fapi_payload})

        def fapi_call_on() -> None:
            fapi_logger_on.info("bench", extra={"payload": fapi_payload})

        # Warmup
        for _ in range(1000):
            std_call()
            fapi_call_off()
            fapi_call_on()

        # Throughput
        std_elapsed, std_rate = _run_throughput(std_call, iterations)
        fapi_elapsed_off, fapi_rate_off = _run_throughput(fapi_call_off, iterations)
        fapi_elapsed_on, fapi_rate_on = _run_throughput(fapi_call_on, iterations)

        # Latency (shorter to reduce timer overhead influence)
        std_lat = _run_latency(std_call, latency_iterations)
        fapi_lat_off = _run_latency(fapi_call_off, latency_iterations)
        fapi_lat_on = _run_latency(fapi_call_on, latency_iterations)

        # Memory (peak tracemalloc during run)
        std_peak = _run_memory(std_call, iterations)
        fapi_peak_off = _run_memory(fapi_call_off, iterations)
        fapi_peak_on = _run_memory(fapi_call_on, iterations)

        # Ensure sinks flush
        with contextlib.suppress(Exception):
            fapi_logger_off.close()
        with contextlib.suppress(Exception):
            fapi_logger_on.close()
        for h in list(std_logger.handlers):
            with contextlib.suppress(Exception):
                h.flush()
            with contextlib.suppress(Exception):
                h.close()
            std_logger.removeHandler(h)

        results["throughput"] = {
            "stdlib_logs_per_sec": std_rate,
            "fapilog_off_logs_per_sec": fapi_rate_off,
            "fapilog_on_logs_per_sec": fapi_rate_on,
            "speedup_factor_off": (fapi_rate_off / std_rate)
            if std_rate > 0
            else float("inf"),
            "speedup_factor_on": (fapi_rate_on / std_rate)
            if std_rate > 0
            else float("inf"),
            "fastpath_speedup_vs_off": (fapi_rate_on / fapi_rate_off)
            if fapi_rate_off > 0
            else float("inf"),
            "stdlib_elapsed_s": std_elapsed,
            "fapilog_off_elapsed_s": fapi_elapsed_off,
            "fapilog_on_elapsed_s": fapi_elapsed_on,
        }

        def _fmt_lat(d: dict[str, float]) -> dict[str, float]:
            return {k: round(v, 3) for k, v in d.items()}

        results["latency_us"] = {
            "stdlib": _fmt_lat(std_lat),
            "fapilog_off": _fmt_lat(fapi_lat_off),
            "fapilog_on": _fmt_lat(fapi_lat_on),
            "reduction_pct_avg_off": _reduction_pct(
                std_lat["avg_us"], fapi_lat_off["avg_us"]
            ),
            "reduction_pct_avg_on": _reduction_pct(
                std_lat["avg_us"], fapi_lat_on["avg_us"]
            ),
            "reduction_pct_median_off": _reduction_pct(
                std_lat["median_us"], fapi_lat_off["median_us"]
            ),
            "reduction_pct_median_on": _reduction_pct(
                std_lat["median_us"], fapi_lat_on["median_us"]
            ),
            "reduction_pct_p95_off": _reduction_pct(
                std_lat["p95_us"], fapi_lat_off["p95_us"]
            ),
            "reduction_pct_p95_on": _reduction_pct(
                std_lat["p95_us"], fapi_lat_on["p95_us"]
            ),
        }

        results["memory_peak_bytes"] = {
            "stdlib": int(std_peak),
            "fapilog_off": int(fapi_peak_off),
            "fapilog_on": int(fapi_peak_on),
            "reduction_pct_off": _reduction_pct(std_peak, fapi_peak_off),
            "reduction_pct_on": _reduction_pct(std_peak, fapi_peak_on),
        }

    return results


def _make_slow_stdlib_logger(file_path: Path, sleep_ms: float) -> logging.Logger:
    class SlowHandler(logging.FileHandler):
        def emit(self, record: logging.LogRecord) -> None:  # type: ignore[override]
            # Simulate slow sink by sleeping per write
            t0 = time.perf_counter()
            try:
                super().emit(record)
            finally:
                dt = sleep_ms / 1000.0
                # Busy sleep keeps closer to requested latency than time.sleep for small values
                while (time.perf_counter() - t0) < dt:
                    pass

    logger = logging.getLogger(f"benchmark_stdlib_slow_{sleep_ms}")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    handler = SlowHandler(file_path, mode="w", encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


async def _slow_async_sink_write(entry: dict, sleep_ms: float) -> None:
    # Simulate constrained sink throughput
    dt = sleep_ms / 1000.0
    if dt > 0:
        await asyncio.sleep(dt)


def enterprise_benchmarks(sleep_ms: float, burst: int) -> dict[str, object]:
    """Enterprise-oriented scenarios:
    - Non-blocking latency under slow sink
    - Burst absorption with backpressure/drops
    """
    from fapilog.core.logger import SyncLoggerFacade

    results: dict[str, object] = {}
    with tempfile.TemporaryDirectory(prefix="fapilog_bench_enterprise_") as tmpdir:
        tmp = Path(tmpdir)
        # stdlib slow sink
        std_slow = _make_slow_stdlib_logger(tmp / "stdlib_slow.log", sleep_ms)

        def std_call() -> None:
            std_slow.info("bench slow")

        # fapilog facade with slow async sink
        logger = SyncLoggerFacade(
            name="bench",
            queue_capacity=10_000,
            batch_max_size=256,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _slow_async_sink_write(e, sleep_ms),
            enrichers=[],
            metrics=None,
        )
        logger.start()

        def fapi_call() -> None:
            logger.info("bench", payload={"x": 1})

        # Measure per-call latency (front-end) under slow sink
        lat_samples = 2000
        std_lat = _run_latency(std_call, lat_samples)
        fapi_lat = _run_latency(fapi_call, lat_samples)
        results["slow_sink_latency_us"] = {
            "sleep_ms": sleep_ms,
            "stdlib": {k: round(v, 3) for k, v in std_lat.items()},
            "fapilog": {k: round(v, 3) for k, v in fapi_lat.items()},
            "fapilog_vs_stdlib_reduction_pct_avg": _reduction_pct(
                std_lat["avg_us"], fapi_lat["avg_us"]
            ),
        }

        # Burst absorption: submit N quickly then drain, capture stats
        start = time.perf_counter()
        for _ in range(burst):
            fapi_call()
        # Drain and collect
        import asyncio as _asyncio

        drain_res = _asyncio.run(logger.stop_and_drain())
        elapsed = time.perf_counter() - start
        results["burst_absorption"] = {
            "burst": burst,
            "submitted": drain_res.submitted,
            "processed": drain_res.processed,
            "dropped": drain_res.dropped,
            "queue_hwm": drain_res.queue_depth_high_watermark,
            "drain_flush_latency_s": round(drain_res.flush_latency_seconds, 6),
            "wall_elapsed_s": round(elapsed, 6),
        }

    return results


def _reduction_pct(baseline: float, contender: float) -> float:
    if baseline <= 0:
        return 0.0
    return round(max(0.0, (baseline - contender) / baseline) * 100.0, 3)


def derive_verdicts(results: dict[str, object]) -> None:
    throughput = results["throughput"]  # type: ignore[assignment]
    latency = results["latency_us"]  # type: ignore[assignment]
    memory = results["memory_peak_bytes"]  # type: ignore[assignment]

    speedup = float(throughput["speedup_factor"])  # type: ignore[index]
    lat_red = float(latency["reduction_pct_avg"])  # type: ignore[index]
    mem_red = float(memory["reduction_pct"])  # type: ignore[index]

    # Claims to evaluate
    claims = [
        (
            "D001",
            "README.md:25",
            "50x throughput improvement over traditional logging",
            "High",
            "Remove unsubstantiated performance claims",
            speedup >= 50.0,
            f"fapilog {throughput['fapilog_logs_per_sec']:.1f} logs/s vs stdlib {throughput['stdlib_logs_per_sec']:.1f} logs/s; speedup {speedup:.2f}x",
        ),
        (
            "D002",
            "README.md:26",
            "90% latency reduction with async-first design",
            "High",
            "Remove unsubstantiated performance claims",
            lat_red >= 90.0,
            f"avg latency reduction {latency['reduction_pct_avg']:.2f}% (median {latency['reduction_pct_median']:.2f}%, p95 {latency['reduction_pct_p95']:.2f}%)",
        ),
        (
            "D003",
            "README.md:27",
            "80% memory reduction with zero-copy operations",
            "High",
            "Remove unsubstantiated performance claims",
            mem_red >= 80.0,
            f"peak memory reduction {memory['reduction_pct']:.2f}% (stdlib {memory['stdlib']} B → fapilog {memory['fapilog']} B)",
        ),
    ]

    # Attach evaluation to results
    results["evaluation"] = []
    for cid, loc, claim, severity, fix, ok, evidence in claims:
        results["evaluation"].append(
            {
                "ID": cid,
                "Doc Location": loc,
                "Claim": claim,
                "Evidence": evidence,
                "Verdict": "True" if ok else "False",
                "Severity": severity,
                "Suggested Fix": ("Keep claim and cite this benchmark" if ok else fix),
            }
        )


def print_markdown_table(results: dict[str, object]) -> None:
    eval_rows = results.get("evaluation", [])  # type: ignore[assignment]
    print(
        "| ID | Doc Location | Claim | Evidence | Verdict | Severity | Suggested Fix |"
    )
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for row in eval_rows:
        print(
            f"| {row['ID']} | {row['Doc Location']} | {row['Claim']} | {row['Evidence']} | {row['Verdict']} | {row['Severity']} | {row['Suggested Fix']} |"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run fapilog vs stdlib logging benchmarks"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=20000,
        help="Iterations for throughput and memory tests",
    )
    parser.add_argument(
        "--latency-iterations",
        type=int,
        default=5000,
        help="Iterations for latency test",
    )
    parser.add_argument(
        "--payload-bytes", type=int, default=256, help="Approx payload size in bytes"
    )
    parser.add_argument(
        "--slow-sink-ms",
        type=float,
        default=2.0,
        help="Simulated sink latency in milliseconds for enterprise tests",
    )
    parser.add_argument(
        "--burst",
        type=int,
        default=20000,
        help="Burst size for enterprise burst absorption test",
    )
    args = parser.parse_args()

    results = benchmark(
        iterations=args.iterations,
        latency_iterations=args.latency_iterations,
        payload_size=args.payload_bytes,
    )
    derive_verdicts(results)

    # Human-friendly output
    print("\n== Raw Results ==")
    print(json.dumps(results, indent=2))

    print("\n== Evaluation Table (Markdown) ==")
    print_markdown_table(results)

    # Enterprise tests
    ent = enterprise_benchmarks(sleep_ms=args.slow_sink_ms, burst=args.burst)
    print("\n== Enterprise Results ==")
    print(json.dumps(ent, indent=2))


if __name__ == "__main__":
    main()
