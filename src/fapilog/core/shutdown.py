"""Graceful shutdown handling for fapilog (Story 6.13, 4.55).

This module provides:
- Atexit handler to drain pending logs on normal exit
- Signal handlers for SIGTERM/SIGINT graceful shutdown
- WeakSet-based logger registration to avoid memory leaks
- Lazy handler installation (Story 4.55) - handlers not installed at import time

The handlers are best-effort - they attempt to flush logs but will not
block indefinitely if draining fails.

Story 4.55: Handlers are installed lazily on first logger start, not at import
time. This avoids conflicts with frameworks (FastAPI, Uvicorn, etc.) that manage
their own signal handlers.
"""

from __future__ import annotations

import asyncio
import atexit
import signal
import sys
import threading
import weakref
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from types import FrameType

    from .logger import AsyncLoggerFacade, SyncLoggerFacade


# Module-level state
_shutdown_in_progress: bool = False
_registered_loggers: weakref.WeakSet[Any] = weakref.WeakSet()
_original_sigterm_handler: Any = None
_original_sigint_handler: Any = None

# Story 4.55: Lazy installation state
_handlers_installed: bool = False
_install_lock = threading.Lock()


def _get_shutdown_settings() -> dict[str, Any]:
    """Get shutdown settings from Settings, with fallback defaults."""
    try:
        from .settings import Settings

        settings = Settings()
        return {
            "atexit_drain_enabled": settings.core.atexit_drain_enabled,
            "atexit_drain_timeout_seconds": settings.core.atexit_drain_timeout_seconds,
            "signal_handler_enabled": settings.core.signal_handler_enabled,
        }
    except Exception:  # pragma: no cover - defensive fallback
        # Fallback to sensible defaults
        return {
            "atexit_drain_enabled": True,
            "atexit_drain_timeout_seconds": 2.0,
            "signal_handler_enabled": True,
        }


def register_logger(
    logger: SyncLoggerFacade | AsyncLoggerFacade,
) -> None:
    """Register a logger for automatic drain on shutdown.

    Uses WeakSet to avoid preventing garbage collection.

    Args:
        logger: Logger facade to register
    """
    _registered_loggers.add(logger)


def unregister_logger(
    logger: SyncLoggerFacade | AsyncLoggerFacade,
) -> None:
    """Unregister a logger from automatic drain.

    Typically called after explicit drain() to avoid double-drain.

    Args:
        logger: Logger facade to unregister
    """
    try:
        _registered_loggers.discard(logger)
    except Exception:  # pragma: no cover - defensive
        pass


def _drain_single_logger(logger: Any, timeout: float) -> None:
    """Drain a single logger with timeout.

    Args:
        logger: Logger facade to drain
        timeout: Maximum seconds to wait for drain
    """
    try:
        coro = logger.stop_and_drain()
        try:
            asyncio.run(asyncio.wait_for(coro, timeout=timeout))
        except asyncio.TimeoutError:
            pass  # Best effort - proceed with exit
        except RuntimeError:
            # Event loop already running - try thread approach
            try:
                import concurrent.futures

                def run_drain(c: Any = coro) -> None:  # pragma: no cover
                    try:
                        asyncio.run(c)
                    except Exception:
                        pass

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    ex.submit(run_drain).result(timeout=timeout)
            except Exception:  # pragma: no cover - executor errors
                pass
    except Exception:
        pass  # Best effort - don't crash on exit


def _atexit_handler() -> None:
    """Best-effort drain of all loggers on normal exit.

    Called by atexit; should never raise.
    """
    global _shutdown_in_progress

    if _shutdown_in_progress:
        return

    settings = _get_shutdown_settings()

    if not settings["atexit_drain_enabled"]:
        return

    _shutdown_in_progress = True
    timeout = settings["atexit_drain_timeout_seconds"]

    # Snapshot the loggers (WeakSet iteration can fail if GC runs)
    try:
        loggers = list(_registered_loggers)
    except Exception:  # pragma: no cover - rare GC race
        return

    for logger in loggers:
        _drain_single_logger(logger, timeout)


def _signal_handler(signum: int, _frame: FrameType | None) -> None:
    """Graceful shutdown on SIGTERM/SIGINT.

    Drains loggers, then re-raises the signal with the default handler
    to allow normal process termination.

    Args:
        signum: Signal number
        _frame: Current stack frame (unused)
    """
    global _shutdown_in_progress

    if _shutdown_in_progress:
        return

    # Drain all loggers
    _atexit_handler()

    # Restore and re-raise the signal for default handling
    try:
        signal.signal(signum, signal.SIG_DFL)
        signal.raise_signal(signum)
    except Exception:  # pragma: no cover - rare signal error
        # If re-raise fails, exit directly
        sys.exit(128 + signum)


def _has_running_event_loop() -> bool:
    """Check if there's already a running event loop.

    When running under ASGI servers (uvicorn, hypercorn, etc.), there's already
    an event loop and the server handles shutdown through lifespan. Installing
    our own signal handlers would interfere with the server's shutdown sequence.
    """
    try:
        loop = asyncio.get_running_loop()
        return loop.is_running()
    except RuntimeError:
        return False


def _do_install_signal_handlers() -> None:
    """Install signal handlers for graceful shutdown.

    Internal function - use install_shutdown_handlers() instead.
    Only installs if enabled in settings, not on Windows (SIGTERM unavailable),
    and not when running under an ASGI server (which handles shutdown via lifespan).
    """
    global _original_sigterm_handler, _original_sigint_handler

    # Skip signal handler installation when running under ASGI servers.
    # These servers (uvicorn, hypercorn, etc.) manage shutdown through lifespan
    # and installing our handlers would interfere with their shutdown sequence.
    if _has_running_event_loop():
        return

    try:
        # SIGINT is available on all platforms
        _original_sigint_handler = signal.signal(signal.SIGINT, _signal_handler)
    except Exception:  # pragma: no cover - rare signal error
        pass

    # SIGTERM is not available on Windows
    if hasattr(signal, "SIGTERM"):
        try:
            _original_sigterm_handler = signal.signal(signal.SIGTERM, _signal_handler)
        except Exception:  # pragma: no cover - rare signal error
            pass


def install_shutdown_handlers() -> bool:
    """Install signal and atexit handlers for graceful shutdown.

    Called automatically on first logger start. Can be called manually
    for early installation or in frameworks that need explicit control.

    This function is idempotent - calling it multiple times has no effect
    after the first successful call.

    Returns:
        True if handlers were installed, False if already installed.

    Example:
        # Install before creating loggers (optional)
        import fapilog
        fapilog.install_shutdown_handlers()

        # Or let it happen automatically
        logger = fapilog.get_logger()  # Installs handlers on first call
    """
    global _handlers_installed

    with _install_lock:
        if _handlers_installed:
            return False

        settings = _get_shutdown_settings()

        if settings["atexit_drain_enabled"]:
            atexit.register(_atexit_handler)

        if settings["signal_handler_enabled"]:
            _do_install_signal_handlers()

        _handlers_installed = True
        return True


def _reset_handler_state() -> None:
    """Reset handler installation state for test isolation.

    This function is intended for use in tests only. It resets the
    _handlers_installed flag to allow re-testing installation behavior.

    Note: This does NOT uninstall already-installed handlers. It only
    resets the flag that tracks whether installation has occurred.
    """
    global _handlers_installed
    _handlers_installed = False


# Story 4.55: No import-time handler installation
# Handlers are installed lazily on first logger start via install_shutdown_handlers()
