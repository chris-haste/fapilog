"""Graceful shutdown handling for fapilog (Story 6.13).

This module provides:
- Atexit handler to drain pending logs on normal exit
- Signal handlers for SIGTERM/SIGINT graceful shutdown
- WeakSet-based logger registration to avoid memory leaks

The handlers are best-effort - they attempt to flush logs but will not
block indefinitely if draining fails.
"""

from __future__ import annotations

import asyncio
import atexit
import signal
import sys
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


def _install_signal_handlers() -> None:
    """Install signal handlers for graceful shutdown.

    Only installs if enabled in settings and not on Windows (SIGTERM unavailable).
    """
    global _original_sigterm_handler, _original_sigint_handler

    settings = _get_shutdown_settings()

    if not settings["signal_handler_enabled"]:
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


# Register atexit handler on module import
atexit.register(_atexit_handler)

# Install signal handlers (if enabled)
_install_signal_handlers()
