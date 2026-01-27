"""Fluent builder API for configuring loggers (Story 10.7)."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .core.logger import AsyncLoggerFacade, SyncLoggerFacade


class LoggerBuilder:
    """Fluent builder for configuring sync loggers.

    Builder accumulates Settings-compatible configuration and creates
    a logger via get_logger() on build().
    """

    def __init__(self) -> None:
        self._config: dict[str, Any] = {}
        self._name: str | None = None
        self._preset: str | None = None
        self._sinks: list[dict[str, Any]] = []

    def with_name(self, name: str) -> LoggerBuilder:
        """Set logger name."""
        self._name = name
        return self

    def with_level(self, level: str) -> LoggerBuilder:
        """Set log level (DEBUG, INFO, WARNING, ERROR)."""
        self._config.setdefault("core", {})["log_level"] = level.upper()
        return self

    def with_preset(self, preset: str) -> LoggerBuilder:
        """Apply preset configuration.

        Preset is applied first, then subsequent methods override.
        Only one preset can be applied.

        Args:
            preset: Preset name (dev, production, fastapi, minimal)

        Raises:
            ValueError: If a preset is already set
        """
        if self._preset is not None:
            raise ValueError(
                f"Preset already set to '{self._preset}'. Cannot apply '{preset}'."
            )
        self._preset = preset
        return self

    def add_file(
        self,
        directory: str,
        *,
        max_bytes: str | int = "10 MB",
        interval: str | int | None = None,
        max_files: int | None = None,
        compress: bool = False,
    ) -> LoggerBuilder:
        """Add rotating file sink.

        Args:
            directory: Log directory (required)
            max_bytes: Max bytes before rotation (supports "10 MB" strings)
            interval: Rotation interval (supports "daily", "1h" strings)
            max_files: Max rotated files to keep
            compress: Compress rotated files

        Raises:
            ValueError: If directory is empty
        """
        if not directory:
            raise ValueError("File sink requires directory parameter")

        file_config: dict[str, Any] = {
            "directory": directory,
            "max_bytes": max_bytes,
        }

        if interval is not None:
            file_config["interval_seconds"] = interval

        if max_files is not None:
            file_config["max_files"] = max_files

        if compress:
            file_config["compress_rotated"] = True

        self._sinks.append({"name": "rotating_file", "config": file_config})
        return self

    def add_stdout(self, *, format: str = "json") -> LoggerBuilder:
        """Add stdout sink.

        Args:
            format: Output format ("json" or "pretty")
        """
        sink_name = "stdout_pretty" if format == "pretty" else "stdout_json"
        self._sinks.append({"name": sink_name})
        return self

    def add_stdout_pretty(self) -> LoggerBuilder:
        """Add pretty-formatted stdout sink (convenience method)."""
        return self.add_stdout(format="pretty")

    def add_http(
        self,
        endpoint: str,
        *,
        timeout: str | float = "30s",
        headers: dict[str, str] | None = None,
    ) -> LoggerBuilder:
        """Add HTTP sink.

        Args:
            endpoint: HTTP endpoint URL (required)
            timeout: Request timeout (supports "30s" strings)
            headers: Additional HTTP headers

        Raises:
            ValueError: If endpoint is empty
        """
        if not endpoint:
            raise ValueError("HTTP sink requires endpoint parameter")

        http_config: dict[str, Any] = {
            "endpoint": endpoint,
            "timeout_seconds": timeout,
        }

        if headers:
            http_config["headers"] = headers

        self._sinks.append({"name": "http", "config": http_config})
        return self

    def add_webhook(
        self,
        endpoint: str,
        *,
        secret: str | None = None,
        timeout: str | float = "5s",
        headers: dict[str, str] | None = None,
    ) -> LoggerBuilder:
        """Add webhook sink.

        Args:
            endpoint: Webhook destination URL (required)
            secret: Shared secret for signing (optional)
            timeout: Request timeout (supports "5s" strings)
            headers: Additional HTTP headers

        Raises:
            ValueError: If endpoint is empty
        """
        if not endpoint:
            raise ValueError("Webhook sink requires endpoint parameter")

        webhook_config: dict[str, Any] = {
            "endpoint": endpoint,
            "timeout_seconds": timeout,
        }

        if secret:
            webhook_config["secret"] = secret

        if headers:
            webhook_config["headers"] = headers

        self._sinks.append({"name": "webhook", "config": webhook_config})
        return self

    def with_redaction(
        self,
        *,
        fields: list[str] | None = None,
        patterns: list[str] | None = None,
    ) -> LoggerBuilder:
        """Configure redaction.

        Fields and patterns are additive - calling multiple times merges values.
        This allows combining presets with custom fields.

        Args:
            fields: Field names to redact (e.g., ["password", "ssn"])
            patterns: Regex patterns to redact (e.g., ["secret.*"])
        """
        redactors = self._config.setdefault("core", {}).setdefault("redactors", [])
        redactor_config = self._config.setdefault("redactor_config", {})

        if fields:
            if "field_mask" not in redactors:
                redactors.append("field_mask")
            existing = redactor_config.setdefault("field_mask", {}).setdefault(
                "fields_to_mask", []
            )
            for field in fields:
                if field not in existing:
                    existing.append(field)

        if patterns:
            if "regex_mask" not in redactors:
                redactors.append("regex_mask")
            existing = redactor_config.setdefault("regex_mask", {}).setdefault(
                "patterns", []
            )
            for pattern in patterns:
                if pattern not in existing:
                    existing.append(pattern)

        return self

    def with_context(self, **kwargs: object) -> LoggerBuilder:
        """Set default bound context.

        Args:
            **kwargs: Context key-value pairs
        """
        self._config.setdefault("core", {})["default_bound_context"] = kwargs
        return self

    def with_enrichers(self, *enrichers: str) -> LoggerBuilder:
        """Enable enrichers by name.

        Args:
            *enrichers: Enricher names (e.g., "runtime_info", "context_vars")
        """
        existing = self._config.setdefault("core", {}).setdefault("enrichers", [])
        existing.extend(enrichers)
        return self

    def with_filters(self, *filters: str) -> LoggerBuilder:
        """Enable filters by name.

        Args:
            *filters: Filter names (e.g., "level", "sampling")
        """
        existing = self._config.setdefault("core", {}).setdefault("filters", [])
        existing.extend(filters)
        return self

    def with_sampling(
        self,
        rate: float = 1.0,
        *,
        seed: int | None = None,
    ) -> LoggerBuilder:
        """Configure probabilistic sampling filter.

        Args:
            rate: Sample rate 0.0-1.0 (1.0 = keep all, 0.1 = keep 10%)
            seed: Random seed for reproducibility

        Example:
            >>> builder.with_sampling(rate=0.1)  # Keep 10% of logs
        """
        filters = self._config.setdefault("core", {}).setdefault("filters", [])
        if "sampling" not in filters:
            filters.append("sampling")

        filter_config = self._config.setdefault("filter_config", {})
        sampling_config: dict[str, Any] = {"sample_rate": rate}
        if seed is not None:
            sampling_config["seed"] = seed
        filter_config["sampling"] = sampling_config

        return self

    def with_adaptive_sampling(
        self,
        min_rate: float = 0.01,
        max_rate: float = 1.0,
        *,
        target_events_per_sec: float = 1000.0,
        window_seconds: float = 60.0,
    ) -> LoggerBuilder:
        """Configure adaptive sampling based on event rate.

        Args:
            min_rate: Minimum sample rate (default: 0.01)
            max_rate: Maximum sample rate (default: 1.0)
            target_events_per_sec: Target event throughput (default: 1000)
            window_seconds: Measurement window (default: 60)

        Example:
            >>> builder.with_adaptive_sampling(target_events_per_sec=500)
        """
        filters = self._config.setdefault("core", {}).setdefault("filters", [])
        if "adaptive_sampling" not in filters:
            filters.append("adaptive_sampling")

        filter_config = self._config.setdefault("filter_config", {})
        filter_config["adaptive_sampling"] = {
            "min_rate": min_rate,
            "max_rate": max_rate,
            "target_events_per_sec": target_events_per_sec,
            "window_seconds": window_seconds,
        }

        return self

    def with_trace_sampling(
        self,
        default_rate: float = 1.0,
        *,
        honor_upstream: bool = True,
    ) -> LoggerBuilder:
        """Configure distributed trace-aware sampling.

        Args:
            default_rate: Default sample rate when no trace context (default: 1.0)
            honor_upstream: Honor upstream sampling decisions (default: True)

        Example:
            >>> builder.with_trace_sampling(default_rate=0.1)
        """
        filters = self._config.setdefault("core", {}).setdefault("filters", [])
        if "trace_sampling" not in filters:
            filters.append("trace_sampling")

        filter_config = self._config.setdefault("filter_config", {})
        filter_config["trace_sampling"] = {
            "default_rate": default_rate,
            "honor_upstream": honor_upstream,
        }

        return self

    def with_rate_limit(
        self,
        capacity: int = 10,
        *,
        refill_rate: float = 5.0,
        key_field: str | None = None,
        max_keys: int = 10000,
        overflow_action: str = "drop",
    ) -> LoggerBuilder:
        """Configure token bucket rate limiting filter.

        Args:
            capacity: Token bucket capacity (default: 10)
            refill_rate: Tokens refilled per second (default: 5.0)
            key_field: Event field for partitioning buckets
            max_keys: Maximum buckets to track (default: 10000)
            overflow_action: Action on overflow ("drop" or "mark")

        Example:
            >>> builder.with_rate_limit(capacity=100, refill_rate=10.0)
        """
        filters = self._config.setdefault("core", {}).setdefault("filters", [])
        if "rate_limit" not in filters:
            filters.append("rate_limit")

        filter_config = self._config.setdefault("filter_config", {})
        rate_limit_config: dict[str, Any] = {
            "capacity": capacity,
            "refill_rate_per_sec": refill_rate,
            "max_keys": max_keys,
            "overflow_action": overflow_action,
        }
        if key_field is not None:
            rate_limit_config["key_field"] = key_field
        filter_config["rate_limit"] = rate_limit_config

        return self

    def with_first_occurrence(
        self,
        window_seconds: float = 300.0,
        *,
        max_entries: int = 10000,
        key_fields: list[str] | None = None,
    ) -> LoggerBuilder:
        """Configure first-occurrence deduplication filter.

        Args:
            window_seconds: Deduplication window (default: 300 = 5 minutes)
            max_entries: Maximum tracked messages (default: 10000)
            key_fields: Fields to use as dedup key (default: message only)

        Example:
            >>> builder.with_first_occurrence(window_seconds=60)
        """
        filters = self._config.setdefault("core", {}).setdefault("filters", [])
        if "first_occurrence" not in filters:
            filters.append("first_occurrence")

        filter_config = self._config.setdefault("filter_config", {})
        first_occurrence_config: dict[str, Any] = {
            "window_seconds": window_seconds,
            "max_entries": max_entries,
        }
        if key_fields is not None:
            first_occurrence_config["key_fields"] = key_fields
        filter_config["first_occurrence"] = first_occurrence_config

        return self

    def with_size_guard(
        self,
        max_bytes: str | int = "256 KB",
        *,
        action: str = "truncate",
        preserve_fields: list[str] | None = None,
    ) -> LoggerBuilder:
        """Configure payload size limiting processor.

        Args:
            max_bytes: Maximum payload size ("256 KB" or 262144)
            action: Action on oversized payloads ("truncate", "drop", "warn")
            preserve_fields: Fields to never remove during truncation

        Example:
            >>> builder.with_size_guard(max_bytes="1 MB", action="truncate")
        """
        processors = self._config.setdefault("core", {}).setdefault("processors", [])
        if "size_guard" not in processors:
            processors.append("size_guard")

        processor_config = self._config.setdefault("processor_config", {})
        size_guard_config: dict[str, Any] = {
            "max_bytes": max_bytes,
            "action": action,
        }
        if preserve_fields is not None:
            size_guard_config["preserve_fields"] = preserve_fields
        else:
            size_guard_config["preserve_fields"] = [
                "level",
                "timestamp",
                "logger",
                "correlation_id",
            ]
        processor_config["size_guard"] = size_guard_config

        return self

    def with_queue_size(self, size: int) -> LoggerBuilder:
        """Set max queue size.

        Args:
            size: Maximum queue size
        """
        self._config.setdefault("core", {})["max_queue_size"] = size
        return self

    def with_batch_size(self, size: int) -> LoggerBuilder:
        """Set batch max size.

        Args:
            size: Maximum batch size
        """
        self._config.setdefault("core", {})["batch_max_size"] = size
        return self

    def with_batch_timeout(self, timeout: str | float) -> LoggerBuilder:
        """Set batch timeout.

        Args:
            timeout: Batch timeout (supports "1s", "500ms" strings)
        """
        from .core.types import _parse_duration

        if isinstance(timeout, str):
            parsed = _parse_duration(timeout)
            if parsed is None:
                raise ValueError(f"Invalid timeout format: {timeout}")
            timeout = parsed
        self._config.setdefault("core", {})["batch_timeout_seconds"] = timeout
        return self

    def _parse_duration(self, value: str | float) -> float:
        """Parse duration from string or float.

        Args:
            value: Duration as string ("30s", "1m") or float seconds

        Returns:
            Duration in seconds as float

        Raises:
            ValueError: If string format is invalid
        """
        if isinstance(value, (int, float)):
            return float(value)

        from .core.types import _parse_duration

        parsed = _parse_duration(value)
        if parsed is None:
            raise ValueError(f"Invalid duration format: {value}")
        return parsed

    def with_circuit_breaker(
        self,
        *,
        enabled: bool = True,
        failure_threshold: int = 5,
        recovery_timeout: str | float = "30s",
    ) -> LoggerBuilder:
        """Configure sink circuit breaker for fault isolation.

        Args:
            enabled: Enable circuit breaker (default: True)
            failure_threshold: Consecutive failures before opening circuit
            recovery_timeout: Time before probing failed sink ("30s" or 30.0)

        Example:
            >>> builder.with_circuit_breaker(enabled=True, failure_threshold=3)
        """
        core = self._config.setdefault("core", {})
        core["sink_circuit_breaker_enabled"] = enabled
        core["sink_circuit_breaker_failure_threshold"] = failure_threshold
        core["sink_circuit_breaker_recovery_timeout_seconds"] = self._parse_duration(
            recovery_timeout
        )
        return self

    def with_backpressure(
        self,
        *,
        wait_ms: int = 50,
        drop_on_full: bool = True,
    ) -> LoggerBuilder:
        """Configure queue backpressure behavior.

        Args:
            wait_ms: Milliseconds to wait for queue space (default: 50)
            drop_on_full: Drop events if queue still full after wait (default: True)

        Example:
            >>> builder.with_backpressure(wait_ms=100, drop_on_full=False)
        """
        core = self._config.setdefault("core", {})
        core["backpressure_wait_ms"] = wait_ms
        core["drop_on_full"] = drop_on_full
        return self

    def with_workers(self, count: int = 1) -> LoggerBuilder:
        """Set number of worker tasks for flush processing.

        Args:
            count: Number of workers (default: 1)

        Example:
            >>> builder.with_workers(count=4)
        """
        self._config.setdefault("core", {})["worker_count"] = count
        return self

    def with_shutdown_timeout(self, timeout: str | float = "3s") -> LoggerBuilder:
        """Set maximum time to flush on shutdown.

        Args:
            timeout: Shutdown timeout ("3s" or 3.0)

        Example:
            >>> builder.with_shutdown_timeout("5s")
        """
        self._config.setdefault("core", {})["shutdown_timeout_seconds"] = (
            self._parse_duration(timeout)
        )
        return self

    def with_atexit_drain(
        self,
        *,
        enabled: bool = True,
        timeout: str | float = "2s",
    ) -> LoggerBuilder:
        """Configure atexit handler for graceful shutdown.

        When enabled, pending logs are drained on normal process exit.

        Args:
            enabled: Enable atexit drain handler (default: True)
            timeout: Maximum seconds to wait for drain ("2s" or 2.0)

        Example:
            >>> builder.with_atexit_drain(enabled=True, timeout="3s")
        """
        core = self._config.setdefault("core", {})
        core["atexit_drain_enabled"] = enabled
        core["atexit_drain_timeout_seconds"] = self._parse_duration(timeout)
        return self

    def with_signal_handlers(self, *, enabled: bool = True) -> LoggerBuilder:
        """Configure signal handlers for graceful shutdown.

        When enabled, SIGTERM and SIGINT trigger graceful log drain
        before process termination.

        Args:
            enabled: Enable signal handlers (default: True)

        Example:
            >>> builder.with_signal_handlers(enabled=True)
        """
        self._config.setdefault("core", {})["signal_handler_enabled"] = enabled
        return self

    def with_flush_on_critical(self, *, enabled: bool = True) -> LoggerBuilder:
        """Configure immediate flush for ERROR/CRITICAL logs.

        When enabled, ERROR and CRITICAL logs bypass batching and are
        flushed immediately to reduce log loss on abrupt shutdown.

        Args:
            enabled: Enable immediate flush for critical logs (default: True)

        Example:
            >>> builder.with_flush_on_critical(enabled=True)
        """
        self._config.setdefault("core", {})["flush_on_critical"] = enabled
        return self

    def with_exceptions(
        self,
        *,
        enabled: bool = True,
        max_frames: int = 10,
        max_stack_chars: int = 20000,
    ) -> LoggerBuilder:
        """Configure exception serialization.

        Args:
            enabled: Enable structured exception capture (default: True)
            max_frames: Maximum stack frames to capture (default: 10)
            max_stack_chars: Maximum total stack string length (default: 20000)

        Example:
            >>> builder.with_exceptions(max_frames=20)
        """
        core = self._config.setdefault("core", {})
        core["exceptions_enabled"] = enabled
        core["exceptions_max_frames"] = max_frames
        core["exceptions_max_stack_chars"] = max_stack_chars
        return self

    def with_parallel_sink_writes(self, enabled: bool = True) -> LoggerBuilder:
        """Enable parallel writes to multiple sinks.

        Args:
            enabled: Write to sinks in parallel (default: True)

        Example:
            >>> builder.with_parallel_sink_writes(enabled=True)
        """
        self._config.setdefault("core", {})["sink_parallel_writes"] = enabled
        return self

    def with_metrics(self, enabled: bool = True) -> LoggerBuilder:
        """Enable Prometheus-compatible metrics.

        Args:
            enabled: Enable metrics collection (default: True)

        Example:
            >>> builder.with_metrics(enabled=True)
        """
        self._config.setdefault("core", {})["enable_metrics"] = enabled
        return self

    def with_error_deduplication(self, window_seconds: float = 5.0) -> LoggerBuilder:
        """Configure error log deduplication.

        Args:
            window_seconds: Seconds to suppress duplicate errors (0 disables)

        Example:
            >>> builder.with_error_deduplication(window_seconds=10.0)
        """
        self._config.setdefault("core", {})["error_dedupe_window_seconds"] = (
            window_seconds
        )
        return self

    def with_diagnostics(
        self,
        *,
        enabled: bool = True,
        output: str = "stderr",
    ) -> LoggerBuilder:
        """Configure internal diagnostics output.

        Args:
            enabled: Enable internal logging (default: True)
            output: Output stream ("stderr" or "stdout")

        Example:
            >>> builder.with_diagnostics(enabled=True, output="stderr")
        """
        core = self._config.setdefault("core", {})
        core["internal_logging_enabled"] = enabled
        core["diagnostics_output"] = output
        return self

    def with_app_name(self, name: str) -> LoggerBuilder:
        """Set application name for log identification.

        Args:
            name: Application name

        Example:
            >>> builder.with_app_name("my-service")
        """
        self._config.setdefault("core", {})["app_name"] = name
        return self

    def with_strict_mode(self, enabled: bool = True) -> LoggerBuilder:
        """Enable strict envelope mode (drop on serialization failure).

        Args:
            enabled: Enable strict mode (default: True)

        Example:
            >>> builder.with_strict_mode(enabled=True)
        """
        self._config.setdefault("core", {})["strict_envelope_mode"] = enabled
        return self

    def with_unhandled_exception_capture(self, enabled: bool = True) -> LoggerBuilder:
        """Enable automatic capture of unhandled exceptions.

        Args:
            enabled: Install exception hooks (default: True)

        Example:
            >>> builder.with_unhandled_exception_capture(enabled=True)
        """
        self._config.setdefault("core", {})["capture_unhandled_enabled"] = enabled
        return self

    def with_routing(
        self,
        rules: list[dict[str, Any]],
        *,
        fallback: list[str] | None = None,
        overlap: bool = True,
    ) -> LoggerBuilder:
        """Configure level-based sink routing.

        Args:
            rules: List of routing rules, each with "levels" and "sinks" keys
            fallback: Sinks to use when no rules match
            overlap: Allow events to match multiple rules (default: True)

        Example:
            >>> builder.with_routing(
            ...     rules=[
            ...         {"levels": ["ERROR"], "sinks": ["cloudwatch"]},
            ...         {"levels": ["INFO", "DEBUG"], "sinks": ["file"]},
            ...     ],
            ...     fallback=["stdout_json"],
            ... )
        """
        routing_config: dict[str, Any] = {
            "enabled": True,
            "rules": rules,
            "overlap": overlap,
        }
        if fallback is not None:
            routing_config["fallback_sinks"] = fallback

        self._config["sink_routing"] = routing_config
        return self

    def with_field_mask(
        self,
        fields: list[str],
        *,
        mask: str = "***",
        block_on_failure: bool = False,
        max_depth: int = 16,
        max_keys: int = 1000,
    ) -> LoggerBuilder:
        """Configure field-based redaction.

        Args:
            fields: Field paths to mask (e.g., ["password", "user.ssn"])
            mask: Replacement string (default: "***")
            block_on_failure: Block log entry if redaction fails (default: False)
            max_depth: Maximum nested depth to scan (default: 16)
            max_keys: Maximum keys to scan (default: 1000)

        Example:
            >>> builder.with_field_mask(["password", "api_key"], mask="[REDACTED]")
        """
        redactors = self._config.setdefault("core", {}).setdefault("redactors", [])
        if "field_mask" not in redactors:
            redactors.append("field_mask")

        redactor_config = self._config.setdefault("redactor_config", {})
        redactor_config["field_mask"] = {
            "fields_to_mask": fields,
            "mask_string": mask,
            "block_on_unredactable": block_on_failure,
            "max_depth": max_depth,
            "max_keys_scanned": max_keys,
        }
        return self

    def with_regex_mask(
        self,
        patterns: list[str],
        *,
        mask: str = "***",
        block_on_failure: bool = False,
        max_depth: int = 16,
        max_keys: int = 1000,
    ) -> LoggerBuilder:
        """Configure regex-based field path redaction.

        Note: Patterns match field PATHS (e.g., "context.password"),
        not field content. Use patterns like "(?i).*password.*".

        Args:
            patterns: Regex patterns to match against field paths
            mask: Replacement string (default: "***")
            block_on_failure: Block log entry if redaction fails (default: False)
            max_depth: Maximum nested depth to scan (default: 16)
            max_keys: Maximum keys to scan (default: 1000)

        Example:
            >>> builder.with_regex_mask(["(?i).*password.*", "(?i).*secret.*"])
        """
        redactors = self._config.setdefault("core", {}).setdefault("redactors", [])
        if "regex_mask" not in redactors:
            redactors.append("regex_mask")

        redactor_config = self._config.setdefault("redactor_config", {})
        redactor_config["regex_mask"] = {
            "patterns": patterns,
            "mask_string": mask,
            "block_on_unredactable": block_on_failure,
            "max_depth": max_depth,
            "max_keys_scanned": max_keys,
        }
        return self

    def with_url_credential_redaction(
        self,
        *,
        enabled: bool = True,
        max_string_length: int = 4096,
    ) -> LoggerBuilder:
        """Configure URL credential redaction.

        Scrubs credentials from URLs like "https://user:pass@host/..."

        Args:
            enabled: Enable URL credential redaction (default: True)
            max_string_length: Max string length to parse (default: 4096)

        Example:
            >>> builder.with_url_credential_redaction(max_string_length=8192)
        """
        redactors = self._config.setdefault("core", {}).setdefault("redactors", [])
        if enabled and "url_credentials" not in redactors:
            redactors.append("url_credentials")
        elif not enabled and "url_credentials" in redactors:
            redactors.remove("url_credentials")

        if enabled:
            redactor_config = self._config.setdefault("redactor_config", {})
            redactor_config["url_credentials"] = {
                "max_string_length": max_string_length,
            }
        return self

    def with_redaction_guardrails(
        self,
        *,
        max_depth: int = 6,
        max_keys: int = 5000,
    ) -> LoggerBuilder:
        """Configure global redaction guardrails.

        Args:
            max_depth: Maximum nested depth for redaction (default: 6)
            max_keys: Maximum keys scanned during redaction (default: 5000)

        Example:
            >>> builder.with_redaction_guardrails(max_depth=10, max_keys=10000)
        """
        core = self._config.setdefault("core", {})
        core["redaction_max_depth"] = max_depth
        core["redaction_max_keys_scanned"] = max_keys
        return self

    def with_redaction_preset(self, preset_name: str) -> LoggerBuilder:
        """Apply a named redaction preset.

        Presets are composable - calling multiple times merges fields.
        Inheritance is resolved at config time (not runtime) for performance.
        Custom fields from with_redaction() extend preset fields.

        Args:
            preset_name: Preset name (e.g., "GDPR_PII", "GDPR_PII_UK", "HIPAA_PHI")

        Raises:
            ValueError: If preset_name is not found.

        Example:
            >>> builder.with_redaction_preset("GDPR_PII")
            >>> builder.with_redaction_preset("GDPR_PII_UK")  # Extends GDPR_PII
            >>> builder.with_redaction_preset("GDPR_PII").with_redaction_preset("PCI_DSS")
        """
        from .redaction import resolve_preset_fields

        # Resolve inheritance at config time (cached for performance)
        fields, patterns = resolve_preset_fields(preset_name)

        # Merge fields and patterns into existing config
        redactors = self._config.setdefault("core", {}).setdefault("redactors", [])
        redactor_config = self._config.setdefault("redactor_config", {})

        # Enable field_mask if we have fields
        if fields:
            if "field_mask" not in redactors:
                redactors.append("field_mask")
            existing_fields = redactor_config.setdefault("field_mask", {}).setdefault(
                "fields_to_mask", []
            )
            # Add with data. prefix for envelope structure
            for field in fields:
                prefixed = f"data.{field}"
                if prefixed not in existing_fields:
                    existing_fields.append(prefixed)

        # Enable regex_mask if we have patterns
        if patterns:
            if "regex_mask" not in redactors:
                redactors.append("regex_mask")
            existing_patterns = redactor_config.setdefault("regex_mask", {}).setdefault(
                "patterns", []
            )
            for pattern in patterns:
                if pattern not in existing_patterns:
                    existing_patterns.append(pattern)

        return self

    def configure_enricher(
        self,
        name: str,
        **config: Any,
    ) -> LoggerBuilder:
        """Configure a specific enricher.

        Args:
            name: Enricher name (e.g., "runtime_info", "context_vars")
            **config: Enricher-specific configuration

        Example:
            >>> builder.configure_enricher("runtime_info", service="my-api")
        """
        enricher_config = self._config.setdefault("enricher_config", {})
        enricher_config[name] = config
        return self

    def with_plugins(
        self,
        *,
        enabled: bool = True,
        allow_external: bool = False,
        allowlist: list[str] | None = None,
        denylist: list[str] | None = None,
        validation_mode: str = "disabled",
    ) -> LoggerBuilder:
        """Configure plugin loading behavior.

        Args:
            enabled: Enable plugin loading (default: True)
            allow_external: Allow entry point plugins (default: False)
            allowlist: Only allow these plugins (empty = all allowed)
            denylist: Block these plugins
            validation_mode: Validation mode ("disabled", "warn", "strict")

        Example:
            >>> builder.with_plugins(allowlist=["rotating_file", "stdout_json"])
        """
        plugins_config: dict[str, Any] = {
            "enabled": enabled,
            "allow_external": allow_external,
            "validation_mode": validation_mode,
        }
        if allowlist is not None:
            plugins_config["allowlist"] = allowlist
        if denylist is not None:
            plugins_config["denylist"] = denylist

        self._config["plugins"] = plugins_config
        return self

    def add_cloudwatch(
        self,
        log_group: str,
        *,
        stream: str | None = None,
        region: str | None = None,
        endpoint_url: str | None = None,
        batch_size: int = 100,
        batch_timeout: str | float = "5s",
        max_retries: int = 3,
        retry_delay: str | float = 0.5,
        create_group: bool = True,
        create_stream: bool = True,
        circuit_breaker: bool = True,
        circuit_breaker_threshold: int = 5,
    ) -> LoggerBuilder:
        """Add AWS CloudWatch Logs sink.

        Args:
            log_group: CloudWatch log group name (required)
            stream: Log stream name (auto-generated if not provided)
            region: AWS region (uses default if not provided)
            endpoint_url: Custom endpoint (e.g., LocalStack)
            batch_size: Events per batch (default: 100)
            batch_timeout: Batch flush timeout ("5s" or 5.0)
            max_retries: Max retries for PutLogEvents (default: 3)
            retry_delay: Base delay for backoff ("0.5s" or 0.5)
            create_group: Create log group if missing (default: True)
            create_stream: Create log stream if missing (default: True)
            circuit_breaker: Enable circuit breaker (default: True)
            circuit_breaker_threshold: Failures before opening (default: 5)

        Example:
            >>> builder.add_cloudwatch("/myapp/prod", region="us-east-1")
        """
        config: dict[str, Any] = {
            "log_group_name": log_group,
            "batch_size": batch_size,
            "batch_timeout_seconds": self._parse_duration(batch_timeout),
            "max_retries": max_retries,
            "retry_base_delay": self._parse_duration(retry_delay),
            "create_log_group": create_group,
            "create_log_stream": create_stream,
            "circuit_breaker_enabled": circuit_breaker,
            "circuit_breaker_threshold": circuit_breaker_threshold,
        }

        if stream is not None:
            config["log_stream_name"] = stream
        if region is not None:
            config["region"] = region
        if endpoint_url is not None:
            config["endpoint_url"] = endpoint_url

        self._sinks.append({"name": "cloudwatch", "config": config})
        return self

    def add_loki(
        self,
        url: str = "http://localhost:3100",
        *,
        tenant_id: str | None = None,
        labels: dict[str, str] | None = None,
        label_keys: list[str] | None = None,
        batch_size: int = 100,
        batch_timeout: str | float = "5s",
        timeout: str | float = "10s",
        max_retries: int = 3,
        retry_delay: str | float = 0.5,
        auth_username: str | None = None,
        auth_password: str | None = None,
        auth_token: str | None = None,
        circuit_breaker: bool = True,
        circuit_breaker_threshold: int = 5,
    ) -> LoggerBuilder:
        """Add Grafana Loki sink.

        Args:
            url: Loki push endpoint (default: http://localhost:3100)
            tenant_id: Multi-tenant identifier
            labels: Static labels for log streams
            label_keys: Event keys to promote to labels
            batch_size: Events per batch (default: 100)
            batch_timeout: Batch flush timeout ("5s" or 5.0)
            timeout: HTTP request timeout ("10s" or 10.0)
            max_retries: Max retries on failure (default: 3)
            retry_delay: Base delay for backoff (0.5 or float)
            auth_username: Basic auth username
            auth_password: Basic auth password
            auth_token: Bearer token
            circuit_breaker: Enable circuit breaker (default: True)
            circuit_breaker_threshold: Failures before opening (default: 5)

        Example:
            >>> builder.add_loki("http://loki:3100", tenant_id="myapp")
        """
        config: dict[str, Any] = {
            "url": url,
            "batch_size": batch_size,
            "batch_timeout_seconds": self._parse_duration(batch_timeout),
            "timeout_seconds": self._parse_duration(timeout),
            "max_retries": max_retries,
            "retry_base_delay": self._parse_duration(retry_delay),
            "circuit_breaker_enabled": circuit_breaker,
            "circuit_breaker_threshold": circuit_breaker_threshold,
        }

        if tenant_id is not None:
            config["tenant_id"] = tenant_id
        if labels is not None:
            config["labels"] = labels
        if label_keys is not None:
            config["label_keys"] = label_keys
        if auth_username is not None:
            config["auth_username"] = auth_username
        if auth_password is not None:
            config["auth_password"] = auth_password
        if auth_token is not None:
            config["auth_token"] = auth_token

        self._sinks.append({"name": "loki", "config": config})
        return self

    def add_postgres(
        self,
        dsn: str | None = None,
        *,
        host: str = "localhost",
        port: int = 5432,
        database: str = "fapilog",
        user: str = "fapilog",
        password: str | None = None,
        table: str = "logs",
        schema: str = "public",
        batch_size: int = 100,
        batch_timeout: str | float = "5s",
        max_retries: int = 3,
        retry_delay: str | float = 0.5,
        min_pool: int = 2,
        max_pool: int = 10,
        pool_acquire_timeout: str | float = "10s",
        create_table: bool = True,
        use_jsonb: bool = True,
        include_raw_json: bool | None = None,
        extract_fields: list[str] | None = None,
        circuit_breaker: bool = True,
        circuit_breaker_threshold: int = 5,
    ) -> LoggerBuilder:
        """Add PostgreSQL sink for structured log storage.

        Args:
            dsn: Full connection string (overrides host/port/database/user/password)
            host: Database host (default: localhost)
            port: Database port (default: 5432)
            database: Database name (default: fapilog)
            user: Database user (default: fapilog)
            password: Database password
            table: Target table name (default: logs)
            schema: Database schema (default: public)
            batch_size: Events per batch (default: 100)
            batch_timeout: Batch flush timeout ("5s" or 5.0)
            max_retries: Max retries on failure (default: 3)
            retry_delay: Base delay for backoff (0.5 or float)
            min_pool: Minimum pool connections (default: 2)
            max_pool: Maximum pool connections (default: 10)
            pool_acquire_timeout: Timeout for acquiring connections ("10s" or 10.0)
            create_table: Auto-create table if missing (default: True)
            use_jsonb: Use JSONB column type (default: True)
            include_raw_json: Store full event JSON payload
            extract_fields: Fields to promote to columns for fast queries
            circuit_breaker: Enable circuit breaker (default: True)
            circuit_breaker_threshold: Failures before opening (default: 5)

        Example:
            >>> builder.add_postgres(dsn="postgresql://user:pass@host/db")
            >>> builder.add_postgres(host="db.example.com", database="logs")
        """
        config: dict[str, Any] = {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "table_name": table,
            "schema_name": schema,
            "batch_size": batch_size,
            "batch_timeout_seconds": self._parse_duration(batch_timeout),
            "max_retries": max_retries,
            "retry_base_delay": self._parse_duration(retry_delay),
            "min_pool_size": min_pool,
            "max_pool_size": max_pool,
            "pool_acquire_timeout": self._parse_duration(pool_acquire_timeout),
            "create_table": create_table,
            "use_jsonb": use_jsonb,
            "circuit_breaker_enabled": circuit_breaker,
            "circuit_breaker_threshold": circuit_breaker_threshold,
        }

        if dsn is not None:
            config["dsn"] = dsn
        if password is not None:
            config["password"] = password
        if include_raw_json is not None:
            config["include_raw_json"] = include_raw_json
        if extract_fields is not None:
            config["extract_fields"] = extract_fields

        self._sinks.append({"name": "postgres", "config": config})
        return self

    def build(self) -> SyncLoggerFacade:
        """Build and return logger.

        Returns:
            SyncLoggerFacade instance

        Raises:
            ValueError: If configuration is invalid
        """
        from . import get_logger
        from .core.settings import Settings

        # Start with preset or empty config
        if self._preset:
            from .core.presets import get_preset

            config = copy.deepcopy(get_preset(self._preset))
            # Merge builder config on top of preset (builder overrides preset)
            self._deep_merge(config, self._config)
        else:
            config = copy.deepcopy(self._config)

        # Add sinks to config
        if self._sinks:
            sink_names = [s["name"] for s in self._sinks]
            config.setdefault("core", {})["sinks"] = sink_names

            # Add sink configs
            sink_config = config.setdefault("sink_config", {})
            for sink in self._sinks:
                if "config" in sink:
                    sink_config[sink["name"]] = sink["config"]

        try:
            settings = Settings(**config)
        except Exception as e:
            raise ValueError(f"Invalid builder configuration: {e}") from e

        return get_logger(name=self._name, settings=settings)

    def _deep_merge(self, base: dict[str, Any], override: dict[str, Any]) -> None:
        """Merge override into base (mutates base). Override wins."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value


class AsyncLoggerBuilder(LoggerBuilder):
    """Fluent builder for configuring async loggers.

    Same API as LoggerBuilder but uses build_async() to create async logger.
    """

    async def build_async(self) -> AsyncLoggerFacade:
        """Build and return async logger.

        Returns:
            AsyncLoggerFacade instance

        Raises:
            ValueError: If configuration is invalid
        """
        from . import get_async_logger
        from .core.settings import Settings

        # Start with preset or empty config
        if self._preset:
            from .core.presets import get_preset

            config = copy.deepcopy(get_preset(self._preset))
            # Merge builder config on top of preset (builder overrides preset)
            self._deep_merge(config, self._config)
        else:
            config = copy.deepcopy(self._config)

        # Add sinks to config
        if self._sinks:
            sink_names = [s["name"] for s in self._sinks]
            config.setdefault("core", {})["sinks"] = sink_names

            # Add sink configs
            sink_config = config.setdefault("sink_config", {})
            for sink in self._sinks:
                if "config" in sink:
                    sink_config[sink["name"]] = sink["config"]

        try:
            settings = Settings(**config)
        except Exception as e:
            raise ValueError(f"Invalid builder configuration: {e}") from e

        return await get_async_logger(name=self._name, settings=settings)
