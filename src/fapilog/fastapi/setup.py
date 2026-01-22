from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncContextManager, AsyncIterator, Callable

from ..core.diagnostics import warn

try:
    from fastapi import FastAPI
except Exception:  # pragma: no cover - optional dependency
    FastAPI = None  # type: ignore

from .context import RequestContextMiddleware
from .logging import LoggingMiddleware

_DrainTimeout = float


def _configure_middleware(
    app: FastAPI,
    *,
    logger: Any,
    skip_paths: list[str] | None = None,
    sample_rate: float = 1.0,
    redact_headers: list[str] | None = None,
    log_errors_on_skip: bool = True,
) -> None:
    """Configure FastAPI middleware in the correct order."""

    def _middleware_name(mw: Any) -> str:
        return getattr(getattr(mw, "cls", None), "__name__", "")

    logging_mw = next(
        (
            mw
            for mw in app.user_middleware
            if _middleware_name(mw) == "LoggingMiddleware"
        ),
        None,
    )
    context_mw = next(
        (
            mw
            for mw in app.user_middleware
            if _middleware_name(mw) == "RequestContextMiddleware"
        ),
        None,
    )
    updated = False
    context_added = False

    if logging_mw is None:
        if context_mw is None:
            app.add_middleware(
                LoggingMiddleware,
                logger=logger,
                skip_paths=skip_paths or [],
                sample_rate=sample_rate,
                redact_headers=redact_headers or [],
                log_errors_on_skip=log_errors_on_skip,
            )
            app.add_middleware(RequestContextMiddleware)
            updated = True
            context_added = True
        else:
            from starlette.middleware import Middleware

            app.user_middleware.insert(
                app.user_middleware.index(context_mw) + 1,
                Middleware(
                    LoggingMiddleware,
                    logger=logger,
                    skip_paths=skip_paths or [],
                    sample_rate=sample_rate,
                    redact_headers=redact_headers or [],
                    log_errors_on_skip=log_errors_on_skip,
                ),
            )
            updated = True
    else:
        if logging_mw.kwargs.get("logger") is None:
            logging_mw.kwargs["logger"] = logger
            updated = True

    if context_mw is None and not context_added:
        app.add_middleware(RequestContextMiddleware)
        updated = True

    if updated and getattr(app, "middleware_stack", None) is not None:
        app.middleware_stack = None


async def _drain_logger(logger: Any, *, timeout: _DrainTimeout = 5.0) -> None:
    """Drain the async logger with a timeout and best-effort warning."""
    try:
        await asyncio.wait_for(logger.drain(), timeout=timeout)
    except asyncio.TimeoutError:
        warn("fastapi", "logger drain timeout", timeout=timeout)
    except Exception:
        warn("fastapi", "logger drain failed")


def setup_logging(
    app: FastAPI | None = None,
    *,
    preset: str | None = None,
    skip_paths: list[str] | None = None,
    sample_rate: float = 1.0,
    redact_headers: list[str] | None = None,
    log_errors_on_skip: bool = True,
    wrap_lifespan: Callable[[FastAPI], AsyncContextManager[None]] | None = None,
    auto_middleware: bool = True,
) -> Callable[[FastAPI], AsyncContextManager[None]]:
    """One-liner FastAPI logging setup.

    Returns an async context manager (lifespan) that:
    - Creates async logger on startup
    - Adds middleware automatically by default (set auto_middleware=False to opt out)
    - Drains logger on shutdown
    - Wraps user's lifespan if provided

    Args:
        app: FastAPI application instance.
        preset: Logger preset name.
        skip_paths: Paths to skip logging for (e.g., ["/health", "/metrics"]).
        sample_rate: Fraction of requests to log (0.0 to 1.0).
        redact_headers: Header names to redact from logs.
        log_errors_on_skip: Whether to log errors on skipped paths (default: True).
        wrap_lifespan: User lifespan to wrap.
        auto_middleware: Whether to auto-configure middleware.
    """
    app_ref = app

    @asynccontextmanager
    async def _lifespan(app_instance: FastAPI) -> AsyncIterator[None]:
        from .. import get_async_logger

        logger = await get_async_logger("fastapi", preset=preset)
        target_app = app_ref or app_instance
        target_app.state.fapilog_logger = logger
        if auto_middleware:
            if getattr(target_app, "middleware_stack", None) is not None:
                # Allow middleware registration during lifespan by forcing a rebuild.
                target_app.middleware_stack = None
            _configure_middleware(
                target_app,
                logger=logger,
                skip_paths=skip_paths,
                sample_rate=sample_rate,
                redact_headers=redact_headers,
                log_errors_on_skip=log_errors_on_skip,
            )
        try:
            if wrap_lifespan is not None:
                async with wrap_lifespan(target_app):
                    yield
            else:
                yield
        finally:
            await _drain_logger(logger)

    return _lifespan


__all__ = ["setup_logging", "_configure_middleware", "_drain_logger"]
