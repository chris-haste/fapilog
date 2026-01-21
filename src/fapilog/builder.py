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

        Args:
            fields: Field names to redact (e.g., ["password", "ssn"])
            patterns: Regex patterns to redact (e.g., ["secret.*"])
        """
        redactors = self._config.setdefault("core", {}).setdefault("redactors", [])
        redactor_config = self._config.setdefault("redactor_config", {})

        if fields:
            if "field_mask" not in redactors:
                redactors.append("field_mask")
            redactor_config.setdefault("field_mask", {})["fields_to_mask"] = fields

        if patterns:
            if "regex_mask" not in redactors:
                redactors.append("regex_mask")
            redactor_config.setdefault("regex_mask", {})["patterns"] = patterns

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
