"""Fluent builder API for configuring loggers (Story 10.7)."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, Literal

from typing_extensions import Self

if TYPE_CHECKING:
    from .core.logger import AsyncLoggerFacade, SyncLoggerFacade


class LoggerBuilder:
    """Fluent builder for configuring sync loggers.

    Builder accumulates Settings-compatible configuration and creates
    a logger via get_logger() on build().
    """

    @staticmethod
    def list_redaction_presets() -> list[str]:
        """List all available redaction preset names.

        Returns:
            Sorted list of preset names (e.g., ["CCPA_PII", "CREDENTIALS", ...]).

        Example:
            >>> LoggerBuilder.list_redaction_presets()
            ['CCPA_PII', 'CONTACT_INFO', 'CREDENTIALS', ...]
        """
        from .redaction import list_redaction_presets

        return list_redaction_presets()

    @staticmethod
    def get_redaction_preset_info(name: str) -> dict[str, Any]:
        """Get detailed information about a redaction preset.

        Args:
            name: The preset name (e.g., "GDPR_PII", "HIPAA_PHI").

        Returns:
            Dictionary with preset metadata:
            - name: Preset name
            - description: Human-readable description
            - fields: List of field names to redact
            - patterns: List of regex patterns
            - extends: List of parent preset names
            - regulation: Compliance regulation (if applicable)
            - region: Geographic region (if applicable)
            - tags: List of tags for filtering

        Raises:
            ValueError: If the preset name is not found.

        Example:
            >>> info = LoggerBuilder.get_redaction_preset_info("GDPR_PII")
            >>> print(info["description"])
            GDPR Article 4 personal data identifiers
        """
        from .redaction import get_redaction_preset, resolve_preset_fields

        preset = get_redaction_preset(name)
        resolved_fields, resolved_patterns = resolve_preset_fields(name)

        return {
            "name": preset.name,
            "description": preset.description,
            "fields": sorted(resolved_fields),
            "patterns": sorted(resolved_patterns),
            "extends": list(preset.extends),
            "regulation": preset.regulation,
            "region": preset.region,
            "tags": list(preset.tags),
        }

    def __init__(self) -> None:
        self._config: dict[str, Any] = {}
        self._name: str | None = None
        self._preset: str | None = None
        self._sinks: list[dict[str, Any]] = []
        self._reuse: bool = True

    def with_name(self, name: str) -> Self:
        """Set logger name."""
        self._name = name
        return self

    def reuse(self, enabled: bool = True) -> Self:
        """Control whether this logger is cached for reuse.

        Args:
            enabled: If True (default), logger is cached by name.
                If False, creates an independent instance that can be
                garbage collected after stop_and_drain().

        Returns:
            Self for method chaining.

        Example:
            >>> # For tests - create isolated logger
            >>> logger = await AsyncLoggerBuilder().reuse(False).build_async()
            >>> await logger.stop_and_drain()
            >>> # Logger can now be garbage collected
        """
        self._reuse = enabled
        return self

    def with_level(self, level: str) -> Self:
        """Set log level (DEBUG, INFO, WARNING, ERROR)."""
        self._config.setdefault("core", {})["log_level"] = level.upper()
        return self

    def with_preset(self, preset: str) -> Self:
        """Apply preset configuration.

        Preset is applied first, then subsequent methods override.
        Only one preset can be applied.

        For production, fastapi, and serverless presets, the CREDENTIALS
        redaction preset is automatically applied for secure defaults.

        For the hardened preset, HIPAA_PHI, PCI_DSS, and CREDENTIALS redaction
        presets are applied for maximum security coverage.

        Args:
            preset: Preset name (dev, production, fastapi, minimal, serverless, hardened)

        Raises:
            ValueError: If a preset is already set
        """
        if self._preset is not None:
            raise ValueError(
                f"Preset already set to '{self._preset}'. Cannot apply '{preset}'."
            )
        self._preset = preset

        # Apply CREDENTIALS redaction preset for security-focused presets
        if preset in ("production", "fastapi", "serverless"):
            self.with_redaction(preset="CREDENTIALS")

        # Apply comprehensive redaction presets for hardened mode
        if preset == "hardened":
            self.with_redaction(preset=["HIPAA_PHI", "PCI_DSS", "CREDENTIALS"])

        return self

    def add_file(
        self,
        directory: str,
        *,
        max_bytes: str | int = "10 MB",
        interval: str | int | None = None,
        max_files: int | None = None,
        compress: bool = False,
    ) -> Self:
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

    def add_stdout(self, *, format: str = "json", capture_mode: bool = False) -> Self:
        """Add stdout sink.

        Args:
            format: Output format ("json" or "pretty")
            capture_mode: If True, skip os.writev() optimization and use buffered
                writes that can be captured via sys.stdout replacement. Useful for
                testing. Only applies to "json" format. Default False.

        Example:
            >>> # For testing with captured output
            >>> logger = LoggerBuilder().add_stdout(capture_mode=True).build()
        """
        sink_name = "stdout_pretty" if format == "pretty" else "stdout_json"
        sink_entry: dict[str, Any] = {"name": sink_name}
        # Only pass capture_mode config for json sink (pretty already uses sys.stdout)
        if sink_name == "stdout_json" and capture_mode:
            sink_entry["config"] = {"capture_mode": True}
        self._sinks.append(sink_entry)
        return self

    def add_stdout_pretty(self) -> Self:
        """Add pretty-formatted stdout sink (convenience method)."""
        return self.add_stdout(format="pretty")

    def add_http(
        self,
        endpoint: str,
        *,
        timeout: str | float = "30s",
        headers: dict[str, str] | None = None,
    ) -> Self:
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
    ) -> Self:
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
        preset: str | list[str] | None = None,
        fields: list[str] | None = None,
        patterns: list[str] | None = None,
        mask: str = "***",
        url_credentials: bool | None = None,
        url_max_length: int = 4096,
        block_on_failure: bool = False,
        max_depth: int | None = None,
        max_keys: int | None = None,
        auto_prefix: bool = True,
        replace: bool = False,
    ) -> Self:
        """Configure redaction with unified API.

        This is the single entry point for all redaction configuration.
        By default, fields and patterns are additive - calling multiple times
        merges values. Use `replace=True` to overwrite instead.

        Args:
            preset: Redaction preset name(s) to apply (e.g., "GDPR_PII", "CREDENTIALS").
                   Can be a single string or list of strings for multiple presets.
            fields: Field names to redact (e.g., ["password", "ssn"]).
            patterns: Regex patterns to match against field paths.
            mask: Replacement string for redacted values (default: "***").
            url_credentials: Enable URL credential redaction (True/False/None).
                            None means no change to current setting.
            url_max_length: Max string length for URL parsing (default: 4096).
            block_on_failure: Block log entry if redaction fails (default: False).
            max_depth: Maximum nested depth for redaction scanning.
            max_keys: Maximum keys to scan during redaction.
            auto_prefix: If True (default), adds "data." prefix to simple field
                        names without dots (e.g., "password" -> "data.password").
            replace: If True, replace existing fields/patterns instead of merging.

        Returns:
            Self for method chaining.

        Example:
            >>> # Apply preset with custom fields
            >>> builder.with_redaction(preset="GDPR_PII", fields=["custom_field"])
            >>>
            >>> # Multiple presets
            >>> builder.with_redaction(preset=["GDPR_PII", "PCI_DSS"])
            >>>
            >>> # Custom patterns with URL credential redaction
            >>> builder.with_redaction(
            ...     patterns=["(?i).*secret.*"],
            ...     url_credentials=True,
            ...     max_depth=10,
            ... )
        """
        from .redaction import resolve_preset_fields

        redactors = self._config.setdefault("core", {}).setdefault("redactors", [])
        redactor_config = self._config.setdefault("redactor_config", {})

        # Collect all fields and patterns
        all_fields: list[str] = []
        all_patterns: list[str] = []

        # Handle preset(s) - preset fields always get data. prefix
        if preset is not None:
            preset_list = [preset] if isinstance(preset, str) else preset
            for preset_name in preset_list:
                resolved_fields, resolved_patterns = resolve_preset_fields(preset_name)
                # Preset fields always get data. prefix for envelope structure
                for field in resolved_fields:
                    all_fields.append(f"data.{field}")
                all_patterns.extend(resolved_patterns)

        # Handle custom fields with auto-prefix
        if fields:
            for field in fields:
                if auto_prefix and "." not in field:
                    all_fields.append(f"data.{field}")
                else:
                    all_fields.append(field)

        # Handle custom patterns
        if patterns:
            all_patterns.extend(patterns)

        # Apply fields
        if all_fields:
            if "field_mask" not in redactors:
                redactors.append("field_mask")
            field_mask_config = redactor_config.setdefault("field_mask", {})
            field_mask_config["mask_string"] = mask
            field_mask_config["block_on_unredactable"] = block_on_failure

            if replace:
                field_mask_config["fields_to_mask"] = list(dict.fromkeys(all_fields))
            else:
                existing = field_mask_config.setdefault("fields_to_mask", [])
                for f in all_fields:
                    if f not in existing:
                        existing.append(f)

        # Apply patterns
        if all_patterns:
            if "regex_mask" not in redactors:
                redactors.append("regex_mask")
            regex_mask_config = redactor_config.setdefault("regex_mask", {})
            regex_mask_config["mask_string"] = mask
            regex_mask_config["block_on_unredactable"] = block_on_failure

            if replace:
                regex_mask_config["patterns"] = list(dict.fromkeys(all_patterns))
            else:
                existing = regex_mask_config.setdefault("patterns", [])
                for p in all_patterns:
                    if p not in existing:
                        existing.append(p)

        # Handle URL credential redaction
        if url_credentials is True:
            if "url_credentials" not in redactors:
                redactors.append("url_credentials")
            url_config = redactor_config.setdefault("url_credentials", {})
            url_config["max_string_length"] = url_max_length
        elif url_credentials is False:
            if "url_credentials" in redactors:
                redactors.remove("url_credentials")

        # Handle guardrails (max_depth and max_keys)
        core = self._config.setdefault("core", {})
        if max_depth is not None:
            core["redaction_max_depth"] = max_depth
        if max_keys is not None:
            core["redaction_max_keys_scanned"] = max_keys

        return self

    def with_context(self, **kwargs: object) -> Self:
        """Set default bound context fields for all log entries.

        Context fields are automatically included in every log entry from this
        logger. Fields are routed to different sections based on their names:

        **Known context fields** (go to ``log.context``):
            request_id, user_id, tenant_id, trace_id, span_id

        **Custom fields** (go to ``log.data``):
            All other field names

        Args:
            **kwargs: Context key-value pairs to bind to the logger.

        Returns:
            Self for method chaining.

        Example:
            >>> logger = LoggerBuilder().with_context(
            ...     request_id="req-123",  # -> log.context.request_id
            ...     custom="value"         # -> log.data.custom
            ... ).build()
        """
        self._config.setdefault("core", {})["default_bound_context"] = kwargs
        return self

    def with_enrichers(self, *enrichers: str) -> Self:
        """Enable enrichers by name.

        Args:
            *enrichers: Enricher names (e.g., "runtime_info", "context_vars")
        """
        existing = self._config.setdefault("core", {}).setdefault("enrichers", [])
        existing.extend(enrichers)
        return self

    def with_filters(self, *filters: str) -> Self:
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
    ) -> Self:
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
    ) -> Self:
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
        # Config keys must match AdaptiveSamplingConfig field names
        filter_config["adaptive_sampling"] = {
            "min_sample_rate": min_rate,
            "max_sample_rate": max_rate,
            "target_eps": target_events_per_sec,
            "window_seconds": window_seconds,
        }

        return self

    def with_trace_sampling(
        self,
        default_rate: float = 1.0,
    ) -> Self:
        """Configure distributed trace-aware sampling.

        Args:
            default_rate: Default sample rate when no trace context (default: 1.0)

        Example:
            >>> builder.with_trace_sampling(default_rate=0.1)
        """
        filters = self._config.setdefault("core", {}).setdefault("filters", [])
        if "trace_sampling" not in filters:
            filters.append("trace_sampling")

        filter_config = self._config.setdefault("filter_config", {})
        # Config key must match TraceSamplingConfig field name
        filter_config["trace_sampling"] = {
            "sample_rate": default_rate,
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
    ) -> Self:
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
        max_keys: int | None = None,
        max_entries: int | None = None,
        key_fields: list[str] | None = None,
    ) -> Self:
        """Configure first-occurrence deduplication filter.

        Args:
            window_seconds: Deduplication window (default: 300 = 5 minutes)
            max_keys: Maximum tracked messages (default: 10000)
            max_entries: Deprecated alias for max_keys
            key_fields: Fields to use as dedup key (default: message only)

        Example:
            >>> builder.with_first_occurrence(window_seconds=60)
        """
        import warnings

        if max_entries is not None:
            warnings.warn(
                "max_entries is deprecated, use max_keys instead",
                DeprecationWarning,
                stacklevel=2,
            )
            if max_keys is None:
                max_keys = max_entries

        if max_keys is None:
            max_keys = 10000

        filters = self._config.setdefault("core", {}).setdefault("filters", [])
        if "first_occurrence" not in filters:
            filters.append("first_occurrence")

        filter_config = self._config.setdefault("filter_config", {})
        first_occurrence_config: dict[str, Any] = {
            "window_seconds": window_seconds,
            "max_keys": max_keys,
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
    ) -> Self:
        """Configure payload size limiting processor.

        Automatically enables ``serialize_in_flush`` since processors operate
        on serialized bytes. If you explicitly set ``serialize_in_flush=False``
        before calling this method, your setting will be preserved (but the
        processor will not execute).

        Args:
            max_bytes: Maximum payload size ("256 KB" or 262144)
            action: Action on oversized payloads ("truncate", "drop", "warn")
            preserve_fields: Fields to never remove during truncation

        Example:
            >>> builder.with_size_guard(max_bytes="1 MB", action="truncate")
        """
        core = self._config.setdefault("core", {})
        processors = core.setdefault("processors", [])
        if "size_guard" not in processors:
            processors.append("size_guard")

        # Enable serialize_in_flush for processors to work (unless explicitly set)
        if "serialize_in_flush" not in core:
            core["serialize_in_flush"] = True

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

    def with_queue_size(self, size: int) -> Self:
        """Set max queue size.

        Args:
            size: Maximum queue size
        """
        self._config.setdefault("core", {})["max_queue_size"] = size
        return self

    def with_batch_size(self, size: int) -> Self:
        """Set batch max size.

        Args:
            size: Maximum batch size
        """
        self._config.setdefault("core", {})["batch_max_size"] = size
        return self

    def with_batch_timeout(self, timeout: str | float) -> Self:
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
    ) -> Self:
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
    ) -> Self:
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

    def with_workers(self, count: int = 1) -> Self:
        """Set number of worker tasks for flush processing.

        Args:
            count: Number of workers (default: 1)

        Example:
            >>> builder.with_workers(count=4)
        """
        self._config.setdefault("core", {})["worker_count"] = count
        return self

    def with_shutdown_timeout(self, timeout: str | float = "3s") -> Self:
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
    ) -> Self:
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

    def with_signal_handlers(self, *, enabled: bool = True) -> Self:
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

    def with_flush_on_critical(self, *, enabled: bool = True) -> Self:
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
    ) -> Self:
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

    def with_parallel_sink_writes(self, enabled: bool = True) -> Self:
        """Enable parallel writes to multiple sinks.

        Args:
            enabled: Write to sinks in parallel (default: True)

        Example:
            >>> builder.with_parallel_sink_writes(enabled=True)
        """
        self._config.setdefault("core", {})["sink_parallel_writes"] = enabled
        return self

    def with_metrics(self, enabled: bool = True) -> Self:
        """Enable Prometheus-compatible metrics.

        Args:
            enabled: Enable metrics collection (default: True)

        Example:
            >>> builder.with_metrics(enabled=True)
        """
        self._config.setdefault("core", {})["enable_metrics"] = enabled
        return self

    def with_error_deduplication(self, window_seconds: float = 5.0) -> Self:
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

    def with_drop_summary(
        self,
        *,
        enabled: bool = True,
        window_seconds: float = 60.0,
    ) -> Self:
        """Configure drop/dedupe visibility summaries.

        When enabled, periodic summary events are logged when events are:
        - Dropped due to backpressure (queue full)
        - Deduplicated due to error dedupe window

        Summary events are marked with `_fapilog_internal: True` and bypass
        the dedupe filter to prevent infinite loops.

        Args:
            enabled: Emit drop/dedupe summary events (default: True)
            window_seconds: Aggregation window in seconds (default: 60.0, min: 1.0)

        Example:
            >>> builder.with_drop_summary()  # Enable with defaults
            >>> builder.with_drop_summary(window_seconds=30.0)  # Custom window
        """
        core = self._config.setdefault("core", {})
        core["emit_drop_summary"] = enabled
        core["drop_summary_window_seconds"] = window_seconds
        return self

    def with_diagnostics(
        self,
        *,
        enabled: bool = True,
        output: str = "stderr",
    ) -> Self:
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

    def with_app_name(self, name: str) -> Self:
        """Set application name for log identification.

        Args:
            name: Application name

        Example:
            >>> builder.with_app_name("my-service")
        """
        self._config.setdefault("core", {})["app_name"] = name
        return self

    def with_strict_mode(self, enabled: bool = True) -> Self:
        """Enable strict envelope mode (drop on serialization failure).

        Args:
            enabled: Enable strict mode (default: True)

        Example:
            >>> builder.with_strict_mode(enabled=True)
        """
        self._config.setdefault("core", {})["strict_envelope_mode"] = enabled
        return self

    def with_unhandled_exception_capture(self, enabled: bool = True) -> Self:
        """Enable automatic capture of unhandled exceptions.

        Args:
            enabled: Install exception hooks (default: True)

        Example:
            >>> builder.with_unhandled_exception_capture(enabled=True)
        """
        self._config.setdefault("core", {})["capture_unhandled_enabled"] = enabled
        return self

    def with_fallback_redaction(
        self,
        *,
        fallback_mode: Literal["inherit", "minimal", "none"] = "minimal",
        fail_mode: Literal["open", "closed", "warn"] = "open",
        scrub_raw: bool = True,
        raw_max_bytes: int | None = None,
    ) -> Self:
        """Configure redaction behavior for fallback and failure scenarios.

        Args:
            fallback_mode: How to redact payloads on stderr fallback.
                - "minimal": Apply built-in sensitive field masking (default)
                - "inherit": Use pipeline redactors (requires pipeline context)
                - "none": No redaction (opt-in to legacy behavior)
            fail_mode: Behavior when redaction pipeline throws exceptions.
                - "open": Pass original event through (default)
                - "closed": Drop event entirely
                - "warn": Pass event through but emit diagnostic warning
            scrub_raw: Apply keyword scrubbing to raw (non-JSON) fallback output.
                Masks patterns like password=, token=, api_key= (default: True).
            raw_max_bytes: Optional byte limit for raw fallback output. Payloads
                exceeding this are truncated with '[truncated]' marker.

        Example:
            >>> builder.with_fallback_redaction(
            ...     fallback_mode="minimal",
            ...     fail_mode="warn",
            ...     scrub_raw=True,
            ...     raw_max_bytes=1000,
            ... )
        """
        core = self._config.setdefault("core", {})
        core["fallback_redact_mode"] = fallback_mode
        core["redaction_fail_mode"] = fail_mode
        core["fallback_scrub_raw"] = scrub_raw
        if raw_max_bytes is not None:
            core["fallback_raw_max_bytes"] = raw_max_bytes
        return self

    def with_routing(
        self,
        rules: list[dict[str, Any]],
        *,
        fallback: list[str] | None = None,
        overlap: bool = True,
    ) -> Self:
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

    def configure_enricher(
        self,
        name: str,
        **config: Any,
    ) -> Self:
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
    ) -> Self:
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
    ) -> Self:
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
    ) -> Self:
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
    ) -> Self:
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

        # Add sinks to config (merge with preset sinks, don't replace)
        if self._sinks:
            sink_names = [s["name"] for s in self._sinks]
            existing_sinks = config.get("core", {}).get("sinks", [])
            # Merge: preset sinks + builder sinks, deduplicated, preserving order
            merged_sinks = list(dict.fromkeys(existing_sinks + sink_names))
            config.setdefault("core", {})["sinks"] = merged_sinks

            # Add sink configs (merge with preset configs, don't replace)
            sink_config = config.setdefault("sink_config", {})
            for sink in self._sinks:
                if "config" in sink:
                    if sink["name"] in sink_config:
                        # Merge: preset config as base, builder config overrides
                        self._deep_merge(sink_config[sink["name"]], sink["config"])
                    else:
                        sink_config[sink["name"]] = sink["config"]

        try:
            settings = Settings(**config)
        except Exception as e:
            raise ValueError(f"Invalid builder configuration: {e}") from e

        return get_logger(name=self._name, settings=settings, reuse=self._reuse)

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

        # Add sinks to config (merge with preset sinks, don't replace)
        if self._sinks:
            sink_names = [s["name"] for s in self._sinks]
            existing_sinks = config.get("core", {}).get("sinks", [])
            # Merge: preset sinks + builder sinks, deduplicated, preserving order
            merged_sinks = list(dict.fromkeys(existing_sinks + sink_names))
            config.setdefault("core", {})["sinks"] = merged_sinks

            # Add sink configs (merge with preset configs, don't replace)
            sink_config = config.setdefault("sink_config", {})
            for sink in self._sinks:
                if "config" in sink:
                    if sink["name"] in sink_config:
                        # Merge: preset config as base, builder config overrides
                        self._deep_merge(sink_config[sink["name"]], sink["config"])
                    else:
                        sink_config[sink["name"]] = sink["config"]

        try:
            settings = Settings(**config)
        except Exception as e:
            raise ValueError(f"Invalid builder configuration: {e}") from e

        return await get_async_logger(
            name=self._name, settings=settings, reuse=self._reuse
        )
