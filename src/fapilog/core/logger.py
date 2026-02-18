"""
Async logging API surface.

For story 2.1a we only define the minimal surface used by tests and
serialization. The full pipeline will be expanded in later stories.
"""

from __future__ import annotations

import asyncio
import contextvars
import threading
import time
import warnings
from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, cast

from ..metrics.metrics import MetricsCollector
from ..plugins.enrichers import BaseEnricher
from ..plugins.processors import BaseProcessor
from ..plugins.redactors import BaseRedactor
from .concurrency import DualQueue
from .envelope import build_envelope
from .events import LogEvent
from .levels import get_level_priority
from .pressure import PressureLevel
from .worker import (
    LoggerWorker,
    stop_plugins,
)

# Sentinel used by unsafe_debug() to distinguish its calls from user kwargs.
# _prepare_payload only injects the _fapilog_unsafe marker when it sees this
# exact object, not a plain True from user kwargs.
_UNSAFE_SENTINEL = object()


class AsyncLogger:
    """Minimal async logger facade used by the core pipeline tests."""

    async def log_many(self, events: Iterable[LogEvent]) -> int:
        """Placeholder batching API for later pipeline integration."""
        return sum(1 for _ in events)


@dataclass(frozen=True)
class AdaptiveDrainSummary:
    """Summary of adaptive pipeline behavior over a logger's lifetime."""

    peak_pressure_level: PressureLevel
    escalation_count: int
    deescalation_count: int
    time_at_level: dict[PressureLevel, float]
    filters_swapped: int
    workers_scaled: int
    peak_workers: int
    batch_resize_count: int


@dataclass
class DrainResult:
    submitted: int
    processed: int
    dropped: int
    retried: int
    queue_depth_high_watermark: int
    flush_latency_seconds: float
    adaptive: AdaptiveDrainSummary | None = None
    backpressure_retries: int = 0


class _WorkerCountersMixin:
    _counters: dict[str, int]

    @property
    def _processed(self) -> int:
        return self._counters.get("processed", 0)

    @_processed.setter
    def _processed(self, value: int) -> None:
        self._counters["processed"] = value

    @property
    def _dropped(self) -> int:
        return self._counters.get("dropped", 0)

    @_dropped.setter
    def _dropped(self, value: int) -> None:
        self._counters["dropped"] = value


class _LoggerMixin(_WorkerCountersMixin):
    """Shared logic between sync and async logger facades."""

    _emit_worker_diagnostics: bool = True

    # Configuration limits - warn if exceeded, but don't reject
    _WARN_NUM_WORKERS = 32
    _WARN_QUEUE_CAPACITY = 1_000_000
    _WARN_BATCH_MAX_SIZE = 10_000

    def _common_init(
        self,
        *,
        name: str | None,
        queue_capacity: int,
        batch_max_size: int,
        batch_timeout_seconds: float,
        backpressure_wait_ms: int,
        drop_on_full: bool,
        sink_write: Any,
        sink_write_serialized: Any | None = None,
        enrichers: list[BaseEnricher] | None = None,
        processors: list[BaseProcessor] | None = None,
        filters: list[Any] | None = None,
        metrics: MetricsCollector | None = None,
        exceptions_enabled: bool = True,
        exceptions_max_frames: int = 50,
        exceptions_max_stack_chars: int = 20000,
        serialize_in_flush: bool = False,
        num_workers: int = 1,
        level_gate: int | None = None,
        emit_drop_summary: bool = False,
        drop_summary_window_seconds: float = 60.0,
        protected_levels: list[str] | None = None,
        protected_queue_size: int | None = None,
    ) -> None:
        # Validate configuration parameters
        self._validate_config(
            queue_capacity=queue_capacity,
            batch_max_size=batch_max_size,
            batch_timeout_seconds=batch_timeout_seconds,
            num_workers=num_workers,
        )

        self._name = name or "root"
        # Include AUDIT and SECURITY by default (Story 1.38)
        default_protected = ["ERROR", "CRITICAL", "FATAL", "AUDIT", "SECURITY"]
        actual_protected = (
            protected_levels if protected_levels is not None else default_protected
        )
        self._protected_levels: frozenset[str] = frozenset(
            lvl.upper() for lvl in actual_protected
        )
        # Use DualQueue for isolated protected-event handling (Story 1.52, 1.56)
        protected_capacity = (
            protected_queue_size
            if protected_queue_size is not None
            else max(100, queue_capacity // 10)
        )
        self._queue: DualQueue[dict[str, Any]] = DualQueue(
            main_capacity=queue_capacity,
            protected_capacity=protected_capacity,
            protected_levels=self._protected_levels,
        )
        self._queue_high_watermark = 0
        self._counters: dict[str, int] = {"processed": 0, "dropped": 0}
        self._batch_max_size = int(batch_max_size)
        self._batch_timeout_seconds = float(batch_timeout_seconds)
        self._drop_on_full = bool(drop_on_full)
        self._sink_write = sink_write
        self._sink_write_serialized = sink_write_serialized
        self._metrics = metrics
        self._enrichers: list[BaseEnricher] = list(enrichers or [])
        self._processors: list[BaseProcessor] = list(processors or [])
        self._filters: list[Any] = list(filters or [])
        self._redactors: list[BaseRedactor] = []

        # Cached component snapshots for worker access (Story 1.40)
        # Tuples are immutable and safe to read from worker thread
        self._filters_snapshot: tuple[Any, ...] = tuple(self._filters)
        self._enrichers_snapshot: tuple[BaseEnricher, ...] = tuple(self._enrichers)
        self._redactors_snapshot: tuple[BaseRedactor, ...] = tuple(self._redactors)
        self._processors_snapshot: tuple[BaseProcessor, ...] = tuple(self._processors)
        self._sinks: list[Any] = []
        self._worker_tasks: list[asyncio.Task[None]] = []
        self._stop_flag = False
        self._worker_loop: asyncio.AbstractEventLoop | None = None
        self._worker_thread: threading.Thread | None = None
        self._thread_ready = threading.Event()
        self._num_workers = max(1, int(num_workers))
        self._drained_event: asyncio.Event | None = None
        self._flush_event: asyncio.Event | None = None
        self._flush_done_event: asyncio.Event | None = None
        self._submitted = 0
        self._retried = 0
        self._backpressure_retries = 0
        self._backpressure_wait_ms = int(backpressure_wait_ms)
        self._serialize_in_flush = bool(serialize_in_flush)
        self._exceptions_enabled = bool(exceptions_enabled)
        self._exceptions_max_frames = int(exceptions_max_frames)
        self._exceptions_max_stack_chars = int(exceptions_max_stack_chars)
        self._bound_context_var: contextvars.ContextVar[dict[str, Any] | None] = (
            contextvars.ContextVar("fapilog_bound_context", default=None)
        )
        self._level_gate: int | None = level_gate
        self._error_dedupe: OrderedDict[str, tuple[float, int]] = OrderedDict()
        self._dedupe_check_count: int = 0
        self._drained: bool = False  # Track if drain() was called (Story 10.29)
        self._started: bool = False  # Track if workers were started (Story 10.29)

        # Adaptive pressure monitoring (Story 1.44)
        self._pressure_monitor: Any | None = None
        self._pressure_monitor_task: asyncio.Task[None] | None = None
        # Adaptive filter ladder (Story 1.45)
        self._adaptive_filter_ladder: dict[Any, tuple[Any, ...]] | None = None
        # Dynamic worker pool (Story 1.46)
        self._worker_pool: Any | None = None
        # Circuit breakers for pressure signal wiring (Story 4.73)
        self._circuit_breakers: list[Any] = []

        # Drop/dedupe summary visibility (Story 12.20)
        self._emit_drop_summary = bool(emit_drop_summary)
        self._drop_summary_window_seconds = float(drop_summary_window_seconds)
        self._drop_count_since_summary: int = 0
        self._last_drop_summary_time: float = 0.0

        # Cache settings values at init to avoid per-call overhead (Story 1.23, 1.25)
        self._cached_sink_concurrency: int = 1
        self._cached_adaptive_enabled: bool = False
        self._cached_adaptive_settings: Any | None = None
        self._cached_adaptive_batch_sizing: bool = False
        self._cached_sampling_rate: float = 1.0
        self._cached_sampling_filters: set[str] = set()
        self._cached_sampling_configured: bool = False
        self._cached_error_dedupe_window: float = 0.0
        self._cached_error_dedupe_max_entries: int = 1000
        self._cached_error_dedupe_ttl_multiplier: float = 10.0
        self._cached_strict_envelope_mode: bool = False
        try:
            from .settings import Settings

            s = Settings()
            self._cached_sampling_rate = float(s.observability.logging.sampling_rate)
            filters = getattr(getattr(s, "core", None), "filters", []) or []
            self._cached_sampling_filters = {
                name.replace("-", "_").lower()
                for name in filters
                if isinstance(name, str)
            }
            self._cached_sampling_configured = bool(
                self._cached_sampling_filters
                & {"sampling", "adaptive_sampling", "trace_sampling"}
            )
            self._cached_error_dedupe_window = float(s.core.error_dedupe_window_seconds)
            self._cached_error_dedupe_max_entries = int(s.core.error_dedupe_max_entries)
            self._cached_error_dedupe_ttl_multiplier = float(
                s.core.error_dedupe_ttl_multiplier
            )
            self._cached_strict_envelope_mode = bool(s.core.strict_envelope_mode)
            self._cached_sink_concurrency = max(1, int(s.core.sink_concurrency))
            # Cache adaptive settings for pressure monitor (Story 1.44)
            _adaptive = getattr(s, "adaptive", None)
            if _adaptive is not None:
                if getattr(_adaptive, "enabled", False) is True:
                    self._cached_adaptive_enabled = True
                    self._cached_adaptive_settings = _adaptive
                # Cache batch_sizing independently (Story 1.47)
                if getattr(_adaptive, "batch_sizing", False) is True:
                    self._cached_adaptive_batch_sizing = True
        except Exception:
            pass

    def _validate_config(
        self,
        *,
        queue_capacity: int,
        batch_max_size: int,
        batch_timeout_seconds: float,
        num_workers: int,
    ) -> None:
        """Validate configuration parameters.

        Raises ValueError for invalid values (zero, negative).
        Emits warnings for unusually high values that may indicate misconfiguration.
        """
        # Strict validation - reject invalid values
        if queue_capacity < 1:
            raise ValueError(f"queue_capacity must be at least 1, got {queue_capacity}")
        if batch_max_size < 1:
            raise ValueError(f"batch_max_size must be at least 1, got {batch_max_size}")
        if batch_timeout_seconds <= 0:
            raise ValueError(
                f"batch_timeout_seconds must be positive, got {batch_timeout_seconds}"
            )
        if num_workers < 1:
            raise ValueError(f"num_workers must be at least 1, got {num_workers}")

        # Soft validation - warn on unusually high values
        warnings_to_emit: list[tuple[str, dict[str, Any]]] = []

        if num_workers > self._WARN_NUM_WORKERS:
            warnings_to_emit.append(
                (
                    f"num_workers={num_workers} exceeds recommended maximum of "
                    f"{self._WARN_NUM_WORKERS}; this may cause thread contention",
                    {
                        "num_workers": num_workers,
                        "recommended_max": self._WARN_NUM_WORKERS,
                    },
                )
            )

        if queue_capacity > self._WARN_QUEUE_CAPACITY:
            warnings_to_emit.append(
                (
                    f"queue_capacity={queue_capacity:,} exceeds recommended maximum of "
                    f"{self._WARN_QUEUE_CAPACITY:,}; this may cause memory exhaustion",
                    {
                        "queue_capacity": queue_capacity,
                        "recommended_max": self._WARN_QUEUE_CAPACITY,
                    },
                )
            )

        if batch_max_size > self._WARN_BATCH_MAX_SIZE:
            warnings_to_emit.append(
                (
                    f"batch_max_size={batch_max_size:,} exceeds recommended maximum of "
                    f"{self._WARN_BATCH_MAX_SIZE:,}; this may cause latency spikes",
                    {
                        "batch_max_size": batch_max_size,
                        "recommended_max": self._WARN_BATCH_MAX_SIZE,
                    },
                )
            )

        if batch_max_size > queue_capacity:
            warnings_to_emit.append(
                (
                    f"batch_max_size={batch_max_size} exceeds queue_capacity={queue_capacity}; "
                    "batches will never reach max size",
                    {
                        "batch_max_size": batch_max_size,
                        "queue_capacity": queue_capacity,
                    },
                )
            )

        # Emit warnings (fail-safe - don't let warning failures break startup)
        for message, context in warnings_to_emit:
            try:
                from .diagnostics import warn

                warn("config", message, _rate_limit_key="config_validation", **context)
            except Exception:
                pass

    def start(self) -> None:
        """Start the logging pipeline in a dedicated background thread.

        Always creates a dedicated thread with its own event loop for the
        logging pipeline. This ensures logging I/O never competes with
        the caller's event loop (e.g., HTTP request handling in FastAPI).

        The only operation on the caller's thread is try_enqueue() —
        microseconds per event.
        """
        if self._worker_loop is not None:
            return
        self._stop_flag = False
        self._started = True  # Mark that workers are being started (Story 10.29)

        # Register with shutdown module for graceful drain (Story 6.13)
        # Also trigger lazy handler installation (Story 4.55)
        try:
            from .shutdown import install_shutdown_handlers, register_logger

            install_shutdown_handlers()  # Lazy install on first logger start
            register_logger(self)  # type: ignore[arg-type]
        except Exception:
            pass  # Fail-open: don't break startup if shutdown module fails

        self._thread_ready.clear()

        def _run() -> None:
            # Create a fresh event loop owned by this thread
            loop_local = asyncio.new_event_loop()
            self._worker_loop = loop_local
            asyncio.set_event_loop(loop_local)
            self._drained_event = asyncio.Event()
            self._flush_event = asyncio.Event()
            self._flush_done_event = asyncio.Event()
            for _ in range(self._num_workers):
                self._worker_tasks.append(loop_local.create_task(self._worker_main()))
            self._maybe_start_pressure_monitor(loop_local)

            # Signal the caller thread that we're ready to accept work
            self._thread_ready.set()
            try:
                # Run until all workers complete. Workers complete when stop_flag
                # is set and they finish draining/flushing. Using run_until_complete
                # instead of run_forever ensures the loop stops only after ALL
                # workers finish, fixing the multi-worker race condition.
                loop_local.run_until_complete(
                    asyncio.gather(*self._worker_tasks, return_exceptions=True)
                )
            finally:
                # Cleanup: cancel pending tasks and close the loop
                try:
                    pending = asyncio.all_tasks(loop_local)
                    for t in pending:
                        t.cancel()
                    if pending:
                        try:
                            cleanup_coro = asyncio.wait_for(
                                asyncio.gather(*pending, return_exceptions=True),
                                timeout=3.0,
                            )
                            loop_local.run_until_complete(cleanup_coro)
                        except Exception:
                            pass
                finally:
                    try:
                        loop_local.close()
                    except Exception:
                        pass

        # Start the worker thread (daemon=True so it won't block process exit)
        self._worker_thread = threading.Thread(target=_run, daemon=True)
        self._worker_thread.start()
        # Wait for the thread to initialize before returning
        self._thread_ready.wait(timeout=2.0)

    def _maybe_start_pressure_monitor(self, loop: asyncio.AbstractEventLoop) -> None:
        """Start PressureMonitor task if adaptive settings are enabled (Story 1.44)."""
        if not self._cached_adaptive_enabled or self._cached_adaptive_settings is None:
            return
        try:
            from .pressure import PressureMonitor

            # Build diagnostic writer that uses the diagnostics module
            def _diag_writer(payload: dict[str, Any]) -> None:
                try:
                    from .diagnostics import warn

                    extra = {
                        k: v
                        for k, v in payload.items()
                        if k not in ("component", "message")
                    }
                    warn(payload["component"], payload["message"], **extra)
                except Exception:
                    pass

            # Build metric setter for the pressure_level gauge
            def _metric_setter(level_idx: int) -> None:
                if self._metrics is not None:
                    try:
                        asyncio.run_coroutine_threadsafe(
                            self._metrics.set_pressure_level(level_idx),
                            loop,
                        )
                    except Exception:
                        pass

            adaptive = self._cached_adaptive_settings
            circuit_boost = getattr(adaptive, "circuit_pressure_boost", 0.20)
            _depth_gauge_setter = None
            _metrics_ref = self._metrics
            if _metrics_ref is not None:

                def _depth_gauge_setter(label: str, depth: int) -> None:
                    self._schedule_metrics_call(
                        _metrics_ref.set_queue_depth, label, depth
                    )

            monitor = PressureMonitor(
                queue=self._queue,
                check_interval_seconds=adaptive.check_interval_seconds,
                cooldown_seconds=adaptive.cooldown_seconds,
                escalate_to_elevated=adaptive.escalate_to_elevated,
                escalate_to_high=adaptive.escalate_to_high,
                escalate_to_critical=adaptive.escalate_to_critical,
                deescalate_from_critical=adaptive.deescalate_from_critical,
                deescalate_from_high=adaptive.deescalate_from_high,
                deescalate_from_elevated=adaptive.deescalate_from_elevated,
                diagnostic_writer=_diag_writer,
                metric_setter=_metric_setter,
                circuit_pressure_boost=circuit_boost,
                depth_gauge_setter=_depth_gauge_setter,
            )
            self._pressure_monitor = monitor

            # Wire circuit breakers to pressure monitor (Story 4.73)
            for breaker in self._circuit_breakers:
                breaker.on_state_change = monitor.on_circuit_state_change

            # Build adaptive filter ladder and register swap callback (Story 1.45)
            # Gated on filter_tightening toggle (Story 1.51)
            if adaptive.filter_tightening:
                try:
                    from .filter_ladder import build_filter_ladder

                    ladder = build_filter_ladder(
                        base_filters=self._filters,
                        protected_levels=self._protected_levels,
                    )
                    self._adaptive_filter_ladder = ladder

                    def _on_filter_change(old_level: Any, new_level: Any) -> None:
                        if self._adaptive_filter_ladder is not None:
                            self._filters_snapshot = self._adaptive_filter_ladder[
                                new_level
                            ]
                            monitor.record_filter_swap()
                            try:
                                from .diagnostics import warn as _diag_warn
                                from .pressure import _LEVELS

                                escalated = _LEVELS.index(new_level) > _LEVELS.index(
                                    old_level
                                )
                                msg = (
                                    "filters tightened"
                                    if escalated
                                    else "filters restored"
                                )
                                _diag_warn(
                                    "adaptive-controller",
                                    msg,
                                    pressure_level=new_level.value,
                                )
                            except Exception:
                                pass

                    monitor.on_level_change(_on_filter_change)
                except Exception:
                    pass  # Fail-open: ladder build failure shouldn't block monitor

            # Build dynamic worker pool and register scaling callback (Story 1.46)
            self._maybe_start_worker_pool(monitor, loop, adaptive)

            self._pressure_monitor_task = loop.create_task(monitor.run())
        except Exception:
            pass  # Fail-open: don't break startup if adaptive module fails

    def _maybe_start_worker_pool(
        self,
        monitor: Any,
        loop: asyncio.AbstractEventLoop,
        adaptive: Any,
    ) -> None:
        """Create WorkerPool and register scaling callback (Story 1.46)."""
        if not adaptive.worker_scaling:
            return
        try:
            from .worker_pool import WorkerPool

            max_workers = getattr(adaptive, "max_workers", 8)

            pool = WorkerPool(
                initial_count=self._num_workers,
                max_workers=max_workers,
                worker_factory=self._make_dynamic_worker,
                loop=loop,
            )
            pool.register_initial_tasks(self._worker_tasks)
            self._worker_pool = pool

            def _on_scaling_change(old_level: Any, new_level: Any) -> None:
                try:
                    target = pool.target_for_level(new_level)
                    pool.scale_to(target)
                    monitor.record_worker_scaling(pool.current_count)
                    try:
                        from .diagnostics import warn as _diag_warn

                        _diag_warn(
                            "adaptive-controller",
                            "workers scaled",
                            pressure_level=new_level.value,
                            worker_count=pool.current_count,
                            dynamic_count=pool.dynamic_count,
                        )
                    except Exception:
                        pass
                except Exception:
                    pass

            monitor.on_level_change(_on_scaling_change)
        except Exception:
            pass  # Fail-open: pool creation failure shouldn't block startup

    async def _make_dynamic_worker(self, stop_flag: Any) -> None:
        """Factory for dynamic worker tasks (Story 1.46).

        Creates a LoggerWorker with a composite stop flag that triggers
        on either the shared drain flag or the individual retirement flag.
        """
        # Create adaptive controller if batch_sizing enabled (Story 1.47)
        adaptive_ctrl = (
            self._make_adaptive_controller()
            if self._cached_adaptive_batch_sizing
            else None
        )
        # Wire batch resize reporter to pressure monitor (Story 10.58)
        batch_resize_reporter = (
            self._pressure_monitor.record_batch_resize
            if self._pressure_monitor is not None and adaptive_ctrl is not None
            else None
        )
        worker = LoggerWorker(
            queue=self._queue,
            batch_max_size=self._batch_max_size,
            batch_timeout_seconds=self._batch_timeout_seconds,
            sink_write=self._sink_write,
            sink_write_serialized=self._sink_write_serialized,
            filters_getter=lambda: self._filters_snapshot,
            enrichers_getter=lambda: self._enrichers_snapshot,
            redactors_getter=lambda: self._redactors_snapshot,
            processors_getter=lambda: self._processors_snapshot,
            metrics=self._metrics,
            serialize_in_flush=self._serialize_in_flush,
            strict_envelope_mode_provider=lambda: self._cached_strict_envelope_mode,
            stop_flag=lambda: self._stop_flag or stop_flag(),
            drained_event=None,
            flush_event=None,
            flush_done_event=None,
            emit_filter_diagnostics=self._emit_worker_diagnostics,
            emit_enricher_diagnostics=self._emit_worker_diagnostics,
            emit_redactor_diagnostics=self._emit_worker_diagnostics,
            emit_processor_diagnostics=self._emit_worker_diagnostics,
            counters=self._counters,
            adaptive_controller=adaptive_ctrl,
            batch_resize_reporter=batch_resize_reporter,
            sink_concurrency=self._cached_sink_concurrency,
        )
        await worker.run(in_thread_mode=True)

    async def _stop_pressure_monitor(self) -> None:
        """Stop the PressureMonitor before draining workers (Story 1.44)."""
        if self._pressure_monitor is not None:
            self._pressure_monitor.stop()
        if self._pressure_monitor_task is not None:
            try:
                await asyncio.wait_for(self._pressure_monitor_task, timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
            except Exception:
                pass
            self._pressure_monitor_task = None

    async def _stop_enrichers_and_redactors(self) -> None:
        """Stop processors, filters, redactors, and enrichers using shared logic."""
        await stop_plugins(
            self._processors,
            self._filters,
            self._redactors,
            self._enrichers,
        )

    def _invalidate_filters_cache(self) -> None:
        """Update filters snapshot after mutation."""
        self._filters_snapshot = tuple(self._filters)

    def _invalidate_enrichers_cache(self) -> None:
        """Update enrichers snapshot after mutation."""
        self._enrichers_snapshot = tuple(self._enrichers)

    def _invalidate_redactors_cache(self) -> None:
        """Update redactors snapshot after mutation."""
        self._redactors_snapshot = tuple(self._redactors)

    def _invalidate_processors_cache(self) -> None:
        """Update processors snapshot after mutation."""
        self._processors_snapshot = tuple(self._processors)

    def _cleanup_resources(self) -> None:
        """Clear internal data structures after drain.

        Releases references to allow garbage collection in long-running
        applications that create/destroy loggers.
        """
        self._error_dedupe.clear()
        self._worker_tasks.clear()
        self._pressure_monitor = None
        self._pressure_monitor_task = None
        self._adaptive_filter_ladder = None
        self._worker_pool = None
        self._enrichers.clear()
        self._processors.clear()
        self._filters.clear()
        self._redactors.clear()
        self._sinks.clear()
        # Clear cached snapshots (Story 1.40)
        self._invalidate_filters_cache()
        self._invalidate_enrichers_cache()
        self._invalidate_redactors_cache()
        self._invalidate_processors_cache()
        if self._metrics is not None:
            self._metrics.cleanup()

    def _prepare_payload(
        self,
        level: str,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> dict[str, Any] | None:
        from .context import request_id_var

        # correlation_id: Only set when explicitly provided via context (Story 1.34)
        # message_id is always generated by build_envelope()
        try:
            current_corr = request_id_var.get()
        except LookupError:
            current_corr = None

        # Use cached settings values (Story 1.23 - avoid Settings() on hot path)
        rate = self._cached_sampling_rate
        if (
            rate < 1.0
            and level in {"DEBUG", "INFO"}
            and not self._cached_sampling_configured
        ):
            import random

            warnings.warn(
                "observability.logging.sampling_rate is deprecated. "
                "Use core.filters=['sampling'] with filter_config.sampling instead.",
                DeprecationWarning,
                stacklevel=3,
            )
            if random.random() > rate:
                return None

        try:
            if level in {"ERROR", "CRITICAL"} and level not in self._protected_levels:
                window = self._cached_error_dedupe_window
                if window > 0.0:
                    import time as _t

                    now = _t.monotonic()
                    max_entries = self._cached_error_dedupe_max_entries

                    # Periodic TTL sweep (Story 1.55)
                    self._dedupe_check_count += 1
                    if self._dedupe_check_count >= 100:
                        self._dedupe_check_count = 0
                        ttl = window * self._cached_error_dedupe_ttl_multiplier
                        cutoff = now - ttl
                        while self._error_dedupe:
                            oldest_key, (oldest_ts, _) = next(
                                iter(self._error_dedupe.items())
                            )
                            if oldest_ts >= cutoff:
                                break
                            del self._error_dedupe[oldest_key]

                    existing = self._error_dedupe.get(message)
                    if existing is None:
                        self._error_dedupe[message] = (now, 0)
                        if len(self._error_dedupe) > max_entries:
                            self._error_dedupe.popitem(last=False)
                    else:
                        first_ts, count = existing
                        if now - first_ts <= window:
                            self._error_dedupe[message] = (first_ts, count + 1)
                            return None
                        if count > 0:
                            from .diagnostics import warn as _warn

                            try:
                                _warn(
                                    "error-dedupe",
                                    "suppressed duplicate errors",
                                    error_message=message,
                                    suppressed=count,
                                    window_seconds=window,
                                )
                            except Exception:
                                pass
                            # Emit dedupe summary event if enabled (Story 12.20)
                            if self._emit_drop_summary:
                                self._schedule_dedupe_summary_emission(
                                    message, count, window
                                )
                        self._error_dedupe[message] = (now, 0)
                        self._error_dedupe.move_to_end(message)
                        if len(self._error_dedupe) > max_entries:
                            self._error_dedupe.popitem(last=False)
        except Exception:
            pass

        try:
            ctx_val = self._bound_context_var.get(None)
            bound_context = dict(ctx_val or {})
        except Exception:
            bound_context = {}

        # Extract _origin from metadata if provided (Story 10.48)
        # _origin is a reserved key for explicit origin override
        from .schema import LogOrigin

        origin: LogOrigin = "native"
        if metadata and "_origin" in metadata:
            origin = cast(LogOrigin, metadata.pop("_origin"))

        # Extract _fapilog_unsafe marker (Story 4.70).
        # Only unsafe_debug() passes the _UNSAFE_SENTINEL; user kwargs
        # with _fapilog_unsafe=True are silently stripped here.
        is_unsafe = (
            metadata is not None
            and metadata.pop("_fapilog_unsafe", None) is _UNSAFE_SENTINEL
        )

        # Delegate envelope construction to envelope module (Story 1.21)
        # build_envelope returns LogEnvelopeV1 (TypedDict) which is structurally
        # compatible with dict[str, Any] - cast for downstream queue compatibility
        payload = cast(
            dict[str, Any],
            build_envelope(
                level=level,
                message=message,
                extra=metadata if metadata else None,
                bound_context=bound_context if bound_context else None,
                exc=exc,
                exc_info=exc_info,
                exceptions_enabled=self._exceptions_enabled,
                exceptions_max_frames=self._exceptions_max_frames,
                exceptions_max_stack_chars=self._exceptions_max_stack_chars,
                logger_name=self._name,
                correlation_id=current_corr,
                origin=origin,
            ),
        )

        # Record sensitive-field count for operational metrics (Story 4.71)
        if self._metrics is not None:
            _sens = payload.get("data", {}).get("sensitive")
            if isinstance(_sens, dict) and _sens:
                self._schedule_metrics_call(
                    self._metrics.record_sensitive_fields, len(_sens)
                )

        # Inject unsafe marker into envelope data for worker to check
        if is_unsafe:
            data = payload.get("data")
            if isinstance(data, dict):
                data["_fapilog_unsafe"] = True
            else:
                payload["data"] = {"_fapilog_unsafe": True}

        self._submitted += 1
        return payload

    def _record_filtered(self, count: int) -> None:
        if self._metrics is None:
            return
        self._schedule_metrics_call(self._metrics.record_events_filtered, count)

    async def _record_filtered_async(self, count: int) -> None:
        if self._metrics is None:
            return
        try:
            await self._metrics.record_events_filtered(count)
        except Exception:
            pass

    def _record_submitted(self, count: int) -> None:
        if self._metrics is None:
            return
        self._schedule_metrics_call(self._metrics.record_events_submitted, count)

    async def _record_submitted_async(self, count: int) -> None:
        if self._metrics is None:
            return
        try:
            await self._metrics.record_events_submitted(count)
        except Exception:
            pass

    def _record_drop_for_summary(self, count: int = 1) -> None:
        """Track drop for summary emission (Story 12.20).

        Called when events are dropped due to backpressure.
        If emit_drop_summary is enabled and the window has elapsed,
        schedules emission of a summary event.
        """
        if not self._emit_drop_summary:
            return

        self._drop_count_since_summary += count

        # Check if window elapsed
        now = time.monotonic()
        if now - self._last_drop_summary_time >= self._drop_summary_window_seconds:
            # Schedule summary emission
            self._schedule_drop_summary_emission()

    def _schedule_drop_summary_emission(self) -> None:
        """Schedule emission of drop summary event."""
        if self._drop_count_since_summary == 0:
            return

        dropped_count = self._drop_count_since_summary
        window = self._drop_summary_window_seconds

        # Reset counters before scheduling to avoid double-counting
        self._drop_count_since_summary = 0
        self._last_drop_summary_time = time.monotonic()

        loop = self._worker_loop
        if loop is not None:
            try:
                asyncio.run_coroutine_threadsafe(
                    self._emit_drop_summary_event(dropped_count, window),
                    loop,
                )
            except Exception:
                pass

    async def _emit_drop_summary_event(
        self, dropped_count: int, window_seconds: float
    ) -> None:
        """Emit a drop summary event directly to sink, bypassing queue.

        The event is marked with _fapilog_internal: True to bypass dedupe
        and be identifiable in logs. We write directly to sink because
        when drops are happening the queue is typically full.
        """
        from .envelope import build_envelope

        payload = cast(
            dict[str, Any],
            build_envelope(
                level="WARNING",
                message="Events dropped due to backpressure",
                extra={
                    "dropped_count": dropped_count,
                    "window_seconds": window_seconds,
                    "_fapilog_internal": True,
                },
                logger_name=self._name,
            ),
        )

        # Write directly to sink, bypassing the queue (which is likely full)
        try:
            await self._sink_write(payload)
        except Exception:
            pass  # Best-effort; don't let summary emission crash the logger

    async def _record_drop_for_summary_async(self, count: int = 1) -> None:
        """Async version of drop tracking for summary emission (Story 12.20)."""
        if not self._emit_drop_summary:
            return

        self._drop_count_since_summary += count

        # Check if window elapsed
        now = time.monotonic()
        if now - self._last_drop_summary_time >= self._drop_summary_window_seconds:
            # Emit summary directly (we're already async)
            if self._drop_count_since_summary > 0:
                dropped_count = self._drop_count_since_summary
                window = self._drop_summary_window_seconds
                self._drop_count_since_summary = 0
                self._last_drop_summary_time = now
                await self._emit_drop_summary_event(dropped_count, window)

    def _schedule_dedupe_summary_emission(
        self, error_message: str, suppressed_count: int, window_seconds: float
    ) -> None:
        """Schedule emission of dedupe summary event (Story 12.20)."""
        loop = self._worker_loop
        if loop is not None:
            try:
                asyncio.run_coroutine_threadsafe(
                    self._emit_dedupe_summary_event(
                        error_message, suppressed_count, window_seconds
                    ),
                    loop,
                )
            except Exception:
                pass

    async def _emit_dedupe_summary_event(
        self, error_message: str, suppressed_count: int, window_seconds: float
    ) -> None:
        """Emit a dedupe summary event directly to sink.

        The event is marked with _fapilog_internal: True to bypass dedupe
        and be identifiable in logs.
        """
        from .envelope import build_envelope

        payload = cast(
            dict[str, Any],
            build_envelope(
                level="INFO",
                message="Errors deduplicated",
                extra={
                    "error_message": error_message,
                    "suppressed_count": suppressed_count,
                    "window_seconds": window_seconds,
                    "_fapilog_internal": True,
                },
                logger_name=self._name,
            ),
        )

        # Write directly to sink
        try:
            await self._sink_write(payload)
        except Exception:
            pass  # Best-effort

    def _make_adaptive_controller(self) -> Any:
        """Create an AdaptiveController for batch sizing (Story 1.47)."""
        from .adaptive import AdaptiveBatchSizer, AdaptiveController

        return AdaptiveController(
            batch_sizer=AdaptiveBatchSizer(
                min_batch=1,
                max_batch=max(self._batch_max_size, 1024),
                target_latency_ms=5.0,
            ),
        )

    def _make_worker(self) -> LoggerWorker:
        # Use cached strict_envelope_mode to avoid Settings() on hot path (Story 1.25)
        cached_strict_mode = self._cached_strict_envelope_mode
        # Create adaptive controller if batch_sizing enabled (Story 1.47)
        adaptive_ctrl = (
            self._make_adaptive_controller()
            if self._cached_adaptive_batch_sizing
            else None
        )
        # Wire batch resize reporter to pressure monitor (Story 10.58)
        batch_resize_reporter = (
            self._pressure_monitor.record_batch_resize
            if self._pressure_monitor is not None and adaptive_ctrl is not None
            else None
        )
        return LoggerWorker(
            queue=self._queue,
            batch_max_size=self._batch_max_size,
            batch_timeout_seconds=self._batch_timeout_seconds,
            sink_write=self._sink_write,
            sink_write_serialized=self._sink_write_serialized,
            # Return cached snapshots instead of creating new lists (Story 1.40)
            filters_getter=lambda: self._filters_snapshot,
            enrichers_getter=lambda: self._enrichers_snapshot,
            redactors_getter=lambda: self._redactors_snapshot,
            processors_getter=lambda: self._processors_snapshot,
            metrics=self._metrics,
            serialize_in_flush=self._serialize_in_flush,
            strict_envelope_mode_provider=lambda: cached_strict_mode,
            stop_flag=lambda: self._stop_flag,
            drained_event=self._drained_event,
            flush_event=self._flush_event,
            flush_done_event=self._flush_done_event,
            emit_filter_diagnostics=self._emit_worker_diagnostics,
            emit_enricher_diagnostics=self._emit_worker_diagnostics,
            emit_redactor_diagnostics=self._emit_worker_diagnostics,
            emit_processor_diagnostics=self._emit_worker_diagnostics,
            counters=self._counters,
            adaptive_controller=adaptive_ctrl,
            batch_resize_reporter=batch_resize_reporter,
            sink_concurrency=self._cached_sink_concurrency,
        )

    async def _worker_main(self) -> None:
        worker = self._make_worker()
        await worker.run(in_thread_mode=True)

    async def _flush_batch(self, batch: list[dict[str, Any]]) -> None:
        worker = self._make_worker()
        await worker.flush_batch(batch)

    async def self_test(self) -> dict[str, Any]:
        """Perform a basic sink readiness probe.

        Calls sink_write with a minimal payload and returns structured result.
        """
        try:
            probe = {
                "level": "DEBUG",
                "message": "self_test",
                "metadata": {},
            }
            await self._sink_write(dict(probe))
            return {"ok": True, "sink": "default"}
        except Exception as exc:  # pragma: no cover - error path
            return {"ok": False, "sink": "default", "error": str(exc)}

    async def check_health(self) -> Any:
        """Aggregated health across enrichers, redactors, and sinks.

        Returns:
            AggregatedHealth with overall status and per-plugin details.
        """
        from ..plugins.health import aggregate_plugin_health

        sinks = getattr(self, "_sinks", None)
        sink_list = sinks if isinstance(sinks, list) and sinks else [self._sink_write]
        return await aggregate_plugin_health(
            enrichers=list(self._enrichers),
            redactors=list(self._redactors),
            filters=list(self._filters),
            processors=list(self._processors),
            sinks=sink_list,
        )

    def _try_enqueue_with_metrics(self, payload: dict[str, Any]) -> bool:
        """Try to enqueue payload, updating high watermark on success.

        This is the hot-path enqueue used by both sync and async facades.
        It calls try_enqueue() on the thread-safe queue and updates the
        high watermark counter if needed. Returns True if enqueued.
        On drop, records protected/unprotected drop metric.
        """
        if self._queue.try_enqueue(payload):
            qsize = self._queue.qsize()
            if qsize > self._queue_high_watermark:
                self._queue_high_watermark = qsize
            return True
        # Record drop metric distinguished by protected status
        if self._metrics is not None:
            level = payload.get("level", "")
            if isinstance(level, str) and level.upper() in self._protected_levels:
                self._schedule_metrics_call(
                    self._metrics.record_events_dropped_protected
                )
            else:
                self._schedule_metrics_call(
                    self._metrics.record_events_dropped_unprotected
                )
        return False

    def _schedule_metrics_call(self, fn: Any, *args: Any, **kwargs: Any) -> None:
        if self._metrics is None:
            return
        loop = self._worker_loop
        if loop is not None:
            try:
                fut = asyncio.run_coroutine_threadsafe(fn(*args, **kwargs), loop)
                _ = fut
                return
            except Exception:
                pass

        def _run() -> None:
            try:
                asyncio.run(fn(*args, **kwargs))
            except Exception:
                return

        threading.Thread(target=_run, daemon=True).start()

    def _drain_thread_mode(self, *, warn_on_timeout: bool) -> DrainResult:
        start = time.perf_counter()
        # Capture adaptive snapshot before stopping monitor (Story 10.58)
        adaptive_summary = (
            self._pressure_monitor.snapshot()
            if self._pressure_monitor is not None
            else None
        )
        # Stop pressure monitor before workers (Story 1.44)
        if self._pressure_monitor is not None:
            self._pressure_monitor.stop()
        # Stop all dynamic workers in pool (Story 1.46)
        if self._worker_pool is not None:
            self._worker_pool.drain_all()
        self._stop_flag = True
        loop = self._worker_loop
        if loop is not None and self._worker_thread is not None:
            # Signal the stop flag to workers via the loop's thread
            try:
                loop.call_soon_threadsafe(lambda: setattr(self, "_stop_flag", True))
            except Exception:
                pass

            # Wait for thread to complete. The thread uses run_until_complete()
            # which returns after all workers finish.
            try:
                timeout = 5.0 if warn_on_timeout else None
                self._worker_thread.join(timeout=timeout)
                if warn_on_timeout and self._worker_thread.is_alive():
                    try:
                        from .diagnostics import warn

                        warn(
                            "logger",
                            "worker thread cleanup timeout",
                            thread_id=self._worker_thread.ident,
                            timeout_seconds=timeout,
                        )
                    except Exception:
                        pass
            except Exception:
                pass

            self._worker_thread = None
            self._worker_loop = None

        # Count any events still in the queue as dropped.
        # This can happen when events are enqueued concurrently with drain
        # after workers have completed their final pass.
        orphaned = 0
        while True:
            ok, _ = self._queue.try_dequeue()
            if not ok:
                break
            orphaned += 1
        if orphaned:
            self._dropped += orphaned

        self._drained = True
        flush_latency = time.perf_counter() - start
        return DrainResult(
            submitted=self._submitted,
            processed=self._processed,
            dropped=self._dropped,
            retried=self._retried,
            queue_depth_high_watermark=self._queue_high_watermark,
            flush_latency_seconds=flush_latency,
            adaptive=adaptive_summary,
            backpressure_retries=self._backpressure_retries,
        )

    def __del__(self) -> None:
        """Warn if logger is garbage collected without being drained.

        This helps users identify resource leaks when loggers are created
        without proper cleanup. The warning is suppressed during interpreter
        shutdown to avoid spurious messages.
        """
        # Guard against interpreter shutdown - sys might be None or finalizing
        try:
            import sys

            if sys.is_finalizing():  # pragma: no cover - shutdown path
                return
        except Exception:  # pragma: no cover - shutdown path
            return

        # Only warn if workers were started but never drained
        # Use getattr for safety - attributes may not exist if __init__ failed
        if getattr(self, "_started", False) and not getattr(self, "_drained", True):
            warnings.warn(
                f"Logger '{self._name}' was garbage collected without calling "
                "drain(). This causes resource leaks. Use runtime_async() context "
                "manager, call drain() explicitly, or use the default name-based "
                "caching (reuse=True).",
                ResourceWarning,
                stacklevel=2,
            )

    def bind(self, **context: Any) -> Any:
        current = {}
        try:
            ctx_val = self._bound_context_var.get(None)
            current = dict(ctx_val or {})
        except Exception:
            current = {}
        current.update(context)
        self._bound_context_var.set(current)
        return self

    def unbind(self, *keys: str) -> Any:
        try:
            ctx_val = self._bound_context_var.get(None)
            current = dict(ctx_val or {})
        except Exception:
            current = {}
        for k in keys:
            current.pop(k, None)
        self._bound_context_var.set(current)
        return self

    def clear_context(self) -> None:
        self._bound_context_var.set(None)

    def enable_enricher(self, enricher: BaseEnricher) -> None:
        try:
            name = getattr(enricher, "name", None)
        except Exception:
            name = None
        if name is None:
            return
        if all(getattr(e, "name", "") != name for e in self._enrichers):
            self._enrichers.append(enricher)
            self._invalidate_enrichers_cache()

    def disable_enricher(self, name: str) -> None:
        self._enrichers = [e for e in self._enrichers if getattr(e, "name", "") != name]
        self._invalidate_enrichers_cache()


class SyncLoggerFacade(_LoggerMixin):
    """Sync facade that enqueues log calls to a background async worker.

    - Non-blocking in async contexts
    - Backpressure policy: wait up to configured ms, then drop
    - Batching: size and time based
    """

    def __init__(
        self,
        *,
        name: str | None,
        queue_capacity: int,
        batch_max_size: int,
        batch_timeout_seconds: float,
        backpressure_wait_ms: int,
        drop_on_full: bool,
        sink_write: Any,
        sink_write_serialized: Any | None = None,
        enrichers: list[BaseEnricher] | None = None,
        processors: list[BaseProcessor] | None = None,
        filters: list[Any] | None = None,
        metrics: MetricsCollector | None = None,
        exceptions_enabled: bool = True,
        exceptions_max_frames: int = 50,
        exceptions_max_stack_chars: int = 20000,
        serialize_in_flush: bool = False,
        num_workers: int = 1,
        level_gate: int | None = None,
        emit_drop_summary: bool = False,
        drop_summary_window_seconds: float = 60.0,
        protected_levels: list[str] | None = None,
        protected_queue_size: int | None = None,
    ) -> None:
        self._common_init(
            name=name,
            queue_capacity=queue_capacity,
            batch_max_size=batch_max_size,
            batch_timeout_seconds=batch_timeout_seconds,
            backpressure_wait_ms=backpressure_wait_ms,
            drop_on_full=drop_on_full,
            sink_write=sink_write,
            sink_write_serialized=sink_write_serialized,
            enrichers=enrichers,
            processors=processors,
            filters=filters,
            metrics=metrics,
            exceptions_enabled=exceptions_enabled,
            exceptions_max_frames=exceptions_max_frames,
            exceptions_max_stack_chars=exceptions_max_stack_chars,
            serialize_in_flush=serialize_in_flush,
            num_workers=num_workers,
            level_gate=level_gate,
            emit_drop_summary=emit_drop_summary,
            drop_summary_window_seconds=drop_summary_window_seconds,
            protected_levels=protected_levels,
            protected_queue_size=protected_queue_size,
        )

    def start(self) -> None:
        """Start the background worker in a dedicated thread.

        Emits a one-time diagnostic when drop_on_full=False is configured,
        noting that backpressure retry adds caller-thread latency.
        """
        if not self._drop_on_full and self._worker_loop is None:
            try:
                from .diagnostics import warn

                warn(
                    "backpressure",
                    "drop_on_full=False configured - caller thread will "
                    f"retry up to {self._backpressure_wait_ms}ms when queue is full",
                    _rate_limit_key="startup-drop-on-full-warning",
                    setting="drop_on_full=False",
                    backpressure_wait_ms=self._backpressure_wait_ms,
                )
            except Exception:
                pass

        super().start()

    async def stop_and_drain(self) -> DrainResult:
        result = await asyncio.to_thread(self._drain_thread_mode, warn_on_timeout=False)
        await self._stop_enrichers_and_redactors()
        self._cleanup_resources()
        return result

    # Public sync API
    def _enqueue(
        self,
        level: str,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        """Enqueue a log event for async processing.

        Prepares the payload and submits it to the worker queue. Handles both
        same-thread and cross-thread submission contexts appropriately.

        Note:
            When called from the worker loop thread (same-thread context), events
            are dropped immediately if the queue is full, regardless of the
            ``drop_on_full`` setting. This prevents deadlock since the thread
            cannot wait on its own event loop. A diagnostic warning is emitted
            when this occurs with ``drop_on_full=False`` to alert users that their
            backpressure configuration cannot be honored in this context.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            message: Log message string.
            exc: Exception instance to include in the log event.
            exc_info: Exception info tuple for traceback extraction.
            **metadata: Additional fields to include in the log event.
        """
        gate = self._level_gate
        if gate is not None:
            priority = get_level_priority(level)
            if priority < gate:
                self._record_filtered(1)
                return

        payload = self._prepare_payload(
            level,
            message,
            exc=exc,
            exc_info=exc_info,
            **metadata,
        )
        if payload is None:
            return

        self._record_submitted(1)
        self.start()
        if self._try_enqueue_with_metrics(payload):
            return

        # Bounded backpressure retry for non-protected events (Story 1.53)
        if not self._drop_on_full:
            level_str = payload.get("level", "")
            is_protected = (
                isinstance(level_str, str)
                and level_str.upper() in self._protected_levels
            )
            if not is_protected:
                budget_ms = self._backpressure_wait_ms
                waited = 0.0
                sleep_ms = 1.0
                while waited < budget_ms:
                    time.sleep(sleep_ms / 1000)
                    waited += sleep_ms
                    if self._try_enqueue_with_metrics(payload):
                        self._backpressure_retries += 1
                        return
                    sleep_ms = min(sleep_ms * 2, 10.0)

        self._dropped += 1
        self._record_drop_for_summary(1)
        try:
            from .diagnostics import warn

            warn(
                "backpressure",
                "drop on full",
                drop_total=self._dropped,
                queue_hwm=self._queue_high_watermark,
                capacity=self._queue.capacity,
            )
        except Exception:
            pass

    def info(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        self._enqueue("INFO", message, exc=exc, exc_info=exc_info, **metadata)

    def debug(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        self._enqueue("DEBUG", message, exc=exc, exc_info=exc_info, **metadata)

    def warning(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        self._enqueue(
            "WARNING",
            message,
            exc=exc,
            exc_info=exc_info,
            **metadata,
        )

    def error(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        self._enqueue("ERROR", message, exc=exc, exc_info=exc_info, **metadata)

    def exception(self, message: str = "", **metadata: Any) -> None:
        """Convenience API: log at ERROR level with current exception info.

        Equivalent to error(message, exc_info=True, **metadata) inside except.
        """
        self._enqueue("ERROR", message, exc_info=True, **metadata)

    def critical(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        """Log a message at CRITICAL level.

        CRITICAL indicates a severe error that may cause the application to
        abort. Use for unrecoverable failures requiring immediate attention.

        Args:
            message: The log message.
            exc: Exception instance to include in the log event.
            exc_info: Exception info tuple or True to capture current exception.
            **metadata: Additional fields to include in the log event.

        Example:
            logger.critical("Database connection lost", db_host="prod-db")
        """
        self._enqueue("CRITICAL", message, exc=exc, exc_info=exc_info, **metadata)

    def audit(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        """Log an audit event for compliance/accountability records.

        AUDIT events are for tracking user actions, data access, and other
        activities that must be recorded for compliance or accountability.

        Args:
            message: The log message describing the audited action.
            exc: Exception instance to include in the log event.
            exc_info: Exception info tuple or True to capture current exception.
            **metadata: Additional fields (user_id, resource, action, etc.).

        Example:
            logger.audit("User login", user_id="123", ip="10.0.0.1")
        """
        self._enqueue("AUDIT", message, exc=exc, exc_info=exc_info, **metadata)

    def security(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        """Log a security event for security-relevant activity.

        SECURITY events are for tracking security-relevant activities such as
        authentication failures, suspicious behavior, or threat indicators.

        Args:
            message: The log message describing the security event.
            exc: Exception instance to include in the log event.
            exc_info: Exception info tuple or True to capture current exception.
            **metadata: Additional fields (user_id, threat_type, source, etc.).

        Example:
            logger.security("Failed auth attempt", user_id="123", attempts=5)
        """
        self._enqueue("SECURITY", message, exc=exc, exc_info=exc_info, **metadata)

    def unsafe_debug(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        """Log raw, unredacted data at DEBUG level.

        Use this for debugging only. The event is tagged with
        ``_fapilog_unsafe=True`` and bypasses the redaction pipeline.
        This method is intentionally named to be visible in code review.

        Args:
            message: The log message describing the raw data.
            exc: Exception instance to include in the log event.
            exc_info: Exception info tuple or True to capture current exception.
            **metadata: Additional fields to include unredacted.

        Example:
            logger.unsafe_debug("raw request", request=raw_req)
        """
        metadata["_fapilog_unsafe"] = _UNSAFE_SENTINEL
        self._enqueue("DEBUG", message, exc=exc, exc_info=exc_info, **metadata)

    # Context binding API
    def bind(self, **context: Any) -> SyncLoggerFacade:
        """Return a child logger with additional bound context for
        current task.

        Binding is additive and scoped to the current async task/thread via
        ContextVar.
        """
        super().bind(**context)
        return self

    def unbind(self, *keys: str) -> SyncLoggerFacade:
        """Remove specific keys from the bound context for current task and return self."""
        super().unbind(*keys)
        return self

    def clear_context(self) -> None:
        """Clear all bound context for current task."""
        super().clear_context()

    # Runtime toggles for enrichers
    def enable_enricher(self, enricher: BaseEnricher) -> None:
        super().enable_enricher(enricher)

    def disable_enricher(self, name: str) -> None:
        super().disable_enricher(name)


class AsyncLoggerFacade(_LoggerMixin):
    """Async facade that enqueues log calls without blocking and honors backpressure.

    - Non-blocking awaitable methods that enqueue without thread hops
    - Binds to current event loop when available
    - Graceful shutdown with flush() and drain() methods
    - Maintains compatibility with existing sync facade patterns
    """

    _emit_worker_diagnostics: bool = False

    def __init__(
        self,
        *,
        name: str | None,
        queue_capacity: int,
        batch_max_size: int,
        batch_timeout_seconds: float,
        backpressure_wait_ms: int,
        drop_on_full: bool,
        sink_write: Any,
        sink_write_serialized: Any | None = None,
        enrichers: list[BaseEnricher] | None = None,
        processors: list[BaseProcessor] | None = None,
        filters: list[Any] | None = None,
        metrics: MetricsCollector | None = None,
        exceptions_enabled: bool = True,
        exceptions_max_frames: int = 50,
        exceptions_max_stack_chars: int = 20000,
        serialize_in_flush: bool = False,
        num_workers: int = 1,
        level_gate: int | None = None,
        emit_drop_summary: bool = False,
        drop_summary_window_seconds: float = 60.0,
        protected_levels: list[str] | None = None,
        protected_queue_size: int | None = None,
    ) -> None:
        self._common_init(
            name=name,
            queue_capacity=queue_capacity,
            batch_max_size=batch_max_size,
            batch_timeout_seconds=batch_timeout_seconds,
            backpressure_wait_ms=backpressure_wait_ms,
            drop_on_full=drop_on_full,
            sink_write=sink_write,
            sink_write_serialized=sink_write_serialized,
            enrichers=enrichers,
            processors=processors,
            filters=filters,
            metrics=metrics,
            exceptions_enabled=exceptions_enabled,
            exceptions_max_frames=exceptions_max_frames,
            exceptions_max_stack_chars=exceptions_max_stack_chars,
            serialize_in_flush=serialize_in_flush,
            num_workers=num_workers,
            level_gate=level_gate,
            emit_drop_summary=emit_drop_summary,
            drop_summary_window_seconds=drop_summary_window_seconds,
            protected_levels=protected_levels,
            protected_queue_size=protected_queue_size,
        )

    async def start_async(self) -> None:
        """Async start that ensures workers are scheduled before returning."""
        self.start()
        if self._worker_loop is not None and self._worker_loop.is_running():
            # Yield to let worker tasks get scheduled on the current loop
            await asyncio.sleep(0)
        elif self._thread_ready.is_set():
            # Threaded start: nothing to await, but ensure the thread signaled ready
            return

    async def flush(self) -> None:
        """Flush current batches without stopping workers.

        This method triggers an immediate flush of the current batch(es) by
        setting an internal flush event and awaiting completion.
        """
        if self._flush_event is None:
            return

        # Clear any prior completion signal
        if self._flush_done_event is not None:
            self._flush_done_event.clear()

        # Set flush event to trigger immediate flush in workers
        self._flush_event.set()

        # Wait for flush to complete (workers will signal done)
        if self._flush_done_event is not None:
            try:
                await asyncio.wait_for(self._flush_done_event.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                # Best-effort: proceed even if workers did not acknowledge
                pass
        # Leave flush_event cleared by workers

    async def drain(self) -> DrainResult:
        """Gracefully stop workers and return DrainResult.

        This method delegates to the existing stop_and_drain() functionality
        and returns the same DrainResult structure.
        """
        return await self.stop_and_drain()

    async def stop_and_drain(self) -> DrainResult:
        result = await asyncio.to_thread(self._drain_thread_mode, warn_on_timeout=False)
        await self._stop_enrichers_and_redactors()
        self._cleanup_resources()
        return result

    # Public async API
    async def _enqueue(
        self,
        level: str,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        gate = self._level_gate
        if gate is not None:
            priority = get_level_priority(level)
            if priority < gate:
                await self._record_filtered_async(1)
                return
        payload = self._prepare_payload(
            level,
            message,
            exc=exc,
            exc_info=exc_info,
            **metadata,
        )
        if payload is None:
            return

        await self._record_submitted_async(1)
        self.start()
        if not self._try_enqueue_with_metrics(payload):
            self._dropped += 1
            self._record_drop_for_summary(1)
            try:
                from .diagnostics import warn

                warn(
                    "backpressure",
                    "drop on full",
                    drop_total=self._dropped,
                    queue_hwm=self._queue_high_watermark,
                    capacity=self._queue.capacity,
                )
            except Exception:
                pass

    async def info(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        await self._enqueue("INFO", message, exc=exc, exc_info=exc_info, **metadata)

    async def debug(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        await self._enqueue("DEBUG", message, exc=exc, exc_info=exc_info, **metadata)

    async def warning(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        await self._enqueue(
            "WARNING",
            message,
            exc=exc,
            exc_info=exc_info,
            **metadata,
        )

    async def error(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        await self._enqueue("ERROR", message, exc=exc, exc_info=exc_info, **metadata)

    async def exception(self, message: str = "", **metadata: Any) -> None:
        """Convenience API: log at ERROR level with current exception info.

        Equivalent to error(message, exc_info=True, **metadata) inside except.
        """
        await self._enqueue("ERROR", message, exc_info=True, **metadata)

    async def critical(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        """Log a message at CRITICAL level.

        CRITICAL indicates a severe error that may cause the application to
        abort. Use for unrecoverable failures requiring immediate attention.

        Args:
            message: The log message.
            exc: Exception instance to include in the log event.
            exc_info: Exception info tuple or True to capture current exception.
            **metadata: Additional fields to include in the log event.

        Example:
            await logger.critical("Database connection lost", db_host="prod-db")
        """
        await self._enqueue("CRITICAL", message, exc=exc, exc_info=exc_info, **metadata)

    async def audit(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        """Log an audit event for compliance/accountability records.

        AUDIT events are for tracking user actions, data access, and other
        activities that must be recorded for compliance or accountability.

        Args:
            message: The log message describing the audited action.
            exc: Exception instance to include in the log event.
            exc_info: Exception info tuple or True to capture current exception.
            **metadata: Additional fields (user_id, resource, action, etc.).

        Example:
            await logger.audit("User login", user_id="123", ip="10.0.0.1")
        """
        await self._enqueue("AUDIT", message, exc=exc, exc_info=exc_info, **metadata)

    async def security(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        """Log a security event for security-relevant activity.

        SECURITY events are for tracking security-relevant activities such as
        authentication failures, suspicious behavior, or threat indicators.

        Args:
            message: The log message describing the security event.
            exc: Exception instance to include in the log event.
            exc_info: Exception info tuple or True to capture current exception.
            **metadata: Additional fields (user_id, threat_type, source, etc.).

        Example:
            await logger.security("Failed auth attempt", user_id="123", attempts=5)
        """
        await self._enqueue("SECURITY", message, exc=exc, exc_info=exc_info, **metadata)

    async def unsafe_debug(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        """Log raw, unredacted data at DEBUG level.

        Use this for debugging only. The event is tagged with
        ``_fapilog_unsafe=True`` and bypasses the redaction pipeline.
        This method is intentionally named to be visible in code review.

        Args:
            message: The log message describing the raw data.
            exc: Exception instance to include in the log event.
            exc_info: Exception info tuple or True to capture current exception.
            **metadata: Additional fields to include unredacted.

        Example:
            await logger.unsafe_debug("raw request", request=raw_req)
        """
        metadata["_fapilog_unsafe"] = _UNSAFE_SENTINEL
        await self._enqueue("DEBUG", message, exc=exc, exc_info=exc_info, **metadata)

    # Context binding API
    def bind(self, **context: Any) -> AsyncLoggerFacade:
        """Return a child logger with additional bound context for
        current task.

        Binding is additive and scoped to the current async task/thread via
        ContextVar.
        """
        super().bind(**context)
        return self

    def unbind(self, *keys: str) -> AsyncLoggerFacade:
        """Remove specific keys from the bound context for current task and return self."""
        super().unbind(*keys)
        return self

    def clear_context(self) -> None:
        """Clear all bound context for current task."""
        super().clear_context()

    # Runtime toggles for enrichers
    def enable_enricher(self, enricher: BaseEnricher) -> None:
        super().enable_enricher(enricher)

    def disable_enricher(self, name: str) -> None:
        super().disable_enricher(name)
