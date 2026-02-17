"""FastAPIBuilder - Unified FastAPI integration with builder pattern (Story 10.52)."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncIterator, Callable

from typing_extensions import Self

from ..builder import AsyncLoggerBuilder
from ..core.diagnostics import warn

if TYPE_CHECKING:
    from contextlib import AbstractAsyncContextManager

try:
    from fastapi import FastAPI
except Exception:  # pragma: no cover - optional dependency
    FastAPI = None  # type: ignore

# FastAPI-specific environment variable mappings
_FASTAPI_ENV_VARS = {
    "skip_paths": ("FAPILOG_FASTAPI__SKIP_PATHS", "list"),
    "allow_headers": ("FAPILOG_FASTAPI__INCLUDE_HEADERS", "list"),
    "sample_rate": ("FAPILOG_FASTAPI__SAMPLE_RATE", "float"),
    "log_errors_on_skip": ("FAPILOG_FASTAPI__LOG_ERRORS_ON_SKIP", "bool"),
}


class FastAPIBuilder(AsyncLoggerBuilder):
    """Builder for FastAPI logging integration.

    Extends AsyncLoggerBuilder with FastAPI-specific methods.
    Use .build() to get a lifespan for FastAPI.

    Example:
        >>> from fapilog.fastapi import FastAPIBuilder
        >>> app = FastAPI(
        ...     lifespan=FastAPIBuilder()
        ...         .with_preset("production")
        ...         .skip_paths(["/health", "/metrics"])
        ...         .include_headers(["content-type"])
        ...         .build()
        ... )
    """

    def __init__(self) -> None:
        super().__init__()
        self._fastapi_config: dict[str, Any] = {}

    def skip_paths(self, paths: list[str]) -> Self:
        """Paths to exclude from request logging.

        Args:
            paths: List of path prefixes to skip (e.g., ["/health", "/metrics"]).

        Returns:
            Self for method chaining.

        Example:
            >>> builder.skip_paths(["/health", "/metrics", "/ready"])
        """
        self._fastapi_config["skip_paths"] = paths
        return self

    def include_headers(self, headers: list[str]) -> Self:
        """Headers to include in request logs (allowlist mode).

        When set, only these headers will be logged. Headers not in this list
        will be excluded from logs.

        Args:
            headers: List of header names to include (case-insensitive).

        Returns:
            Self for method chaining.

        Example:
            >>> builder.include_headers(["content-type", "user-agent", "accept"])
        """
        self._fastapi_config["allow_headers"] = headers
        return self

    def with_correlation_id(
        self,
        *,
        header: str = "X-Request-ID",
        generate: bool = True,
        propagate: bool = True,
        inject_response: bool = True,
    ) -> Self:
        """Configure correlation ID handling.

        Args:
            header: Header name to read/write correlation ID (default: X-Request-ID).
            generate: Whether to generate ID if not present (default: True).
            propagate: Whether to propagate ID to child contexts (default: True).
            inject_response: Whether to add ID to response headers (default: True).

        Returns:
            Self for method chaining.

        Example:
            >>> builder.with_correlation_id(
            ...     header="X-Correlation-ID",
            ...     generate=True,
            ...     propagate=True,
            ... )
        """
        self._fastapi_config["correlation_id"] = {
            "header": header,
            "generate": generate,
            "propagate": propagate,
            "inject_response": inject_response,
        }
        return self

    def sample_rate(self, rate: float) -> Self:
        """Request-level sampling rate.

        Controls what fraction of requests are logged. This is separate from
        the log-level sampling configured via with_sampling().

        Args:
            rate: Fraction of requests to log (0.0 to 1.0).
                  0.0 = no requests, 1.0 = all requests.

        Returns:
            Self for method chaining.

        Example:
            >>> builder.sample_rate(0.1)  # Log 10% of requests
        """
        self._fastapi_config["sample_rate"] = rate
        return self

    def log_errors_on_skip(self, enabled: bool = True) -> Self:
        """Log errors even on skipped paths.

        When enabled, error responses (5xx) are logged even for paths in
        skip_paths. This ensures errors are visible in logs regardless of
        the skip configuration.

        Args:
            enabled: Whether to log errors on skipped paths (default: True).

        Returns:
            Self for method chaining.

        Example:
            >>> builder.skip_paths(["/health"]).log_errors_on_skip(True)
        """
        self._fastapi_config["log_errors_on_skip"] = enabled
        return self

    def _apply_fastapi_env_vars(self) -> None:
        """Apply FastAPI-specific environment variables to config.

        Environment variables have priority over code-specified values.
        """
        for field_name, (env_var, field_type) in _FASTAPI_ENV_VARS.items():
            value = os.getenv(env_var)
            if value is None:
                continue

            converted = _convert_env_value(value, field_type)
            if converted is not None:
                self._fastapi_config[field_name] = converted

    def _detect_env_overrides(self) -> list[str]:
        """Detect config values that would be overridden by env vars.

        Returns:
            List of override descriptions for warning emission.
        """
        overrides: list[str] = []
        for field_name, (env_var, field_type) in _FASTAPI_ENV_VARS.items():
            env_value_raw = os.getenv(env_var)
            if env_value_raw is None:
                continue

            code_value = self._fastapi_config.get(field_name)
            if code_value is None:
                continue

            env_value = _convert_env_value(env_value_raw, field_type)
            if env_value is not None and env_value != code_value:
                overrides.append(
                    f"{field_name}={code_value} overridden by {env_var}={env_value}"
                )

        return overrides

    def build(  # type: ignore[override]
        self,
    ) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
        """Build and return a FastAPI lifespan.

        Creates a lifespan callable that:
        - Configures the async logger on startup
        - Adds logging and context middleware
        - Drains the logger on shutdown

        Environment variables take priority over code-specified values.
        A warning is emitted via internal diagnostics when an env var
        overrides a code-specified value.

        Returns:
            Callable that accepts a FastAPI app and returns an async context manager.

        Example:
            >>> lifespan = FastAPIBuilder().with_preset("production").build()
            >>> app = FastAPI(lifespan=lifespan)
        """
        # Emit warnings for env var overrides (AC5)
        for override in self._detect_env_overrides():
            warn("fastapi", f"Config override: {override}")

        # Apply env vars (they override code-specified values) (AC4, AC6)
        self._apply_fastapi_env_vars()

        # Capture configuration at build time
        fastapi_config = dict(self._fastapi_config)
        builder_config = dict(self._config)
        preset = self._preset
        sinks = list(self._sinks)
        name = self._name
        reuse = self._reuse

        @asynccontextmanager
        async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
            import copy

            # Build logger using parent class logic
            from .. import get_async_logger
            from ..core.presets import get_preset
            from ..core.settings import Settings
            from .setup import _configure_middleware, _drain_logger

            # Start with preset or empty config
            if preset:
                config = copy.deepcopy(get_preset(preset))
                # Deep merge builder config on top of preset
                _deep_merge(config, builder_config)
            else:
                config = copy.deepcopy(builder_config)

            # Add sinks to config
            if sinks:
                sink_names = [s["name"] for s in sinks]
                existing_sinks = config.get("core", {}).get("sinks", [])
                merged_sinks = list(dict.fromkeys(existing_sinks + sink_names))
                config.setdefault("core", {})["sinks"] = merged_sinks

                sink_config = config.setdefault("sink_config", {})
                for sink in sinks:
                    if "config" in sink:
                        if sink["name"] in sink_config:
                            _deep_merge(sink_config[sink["name"]], sink["config"])
                        else:
                            sink_config[sink["name"]] = sink["config"]

            try:
                settings = Settings(**config)
            except Exception as e:
                raise ValueError(f"Invalid builder configuration: {e}") from e

            logger = await get_async_logger(name=name, settings=settings, reuse=reuse)

            app.state.fapilog_logger = logger

            # Allow middleware registration during lifespan by forcing a rebuild
            if getattr(app, "middleware_stack", None) is not None:
                app.middleware_stack = None

            # Configure middleware with FastAPI-specific settings
            _configure_middleware(
                app,
                logger=logger,
                skip_paths=fastapi_config.get("skip_paths"),
                sample_rate=fastapi_config.get("sample_rate", 1.0),
                log_errors_on_skip=fastapi_config.get("log_errors_on_skip", True),
                allow_headers=fastapi_config.get("allow_headers"),
            )

            try:
                yield
            finally:
                await _drain_logger(logger)

        return _lifespan


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    """Deep merge override into base dict (mutates base)."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _convert_env_value(value: str, field_type: str) -> Any:
    """Convert a string environment variable value to the target type.

    Args:
        value: The raw string value from the environment.
        field_type: The target type ("list", "float", "bool").

    Returns:
        The converted value, or None if conversion fails.
    """
    try:
        if field_type == "list":
            stripped = value.strip()
            if not stripped:
                return []
            return [v for v in (item.strip() for item in stripped.split(",")) if v]

        if field_type == "float":
            return float(value)

        if field_type == "bool":
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
            return None

    except Exception:
        return None

    return None
