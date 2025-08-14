from __future__ import annotations

import asyncio
import signal
from typing import Any

from .diagnostics import warn


def install_signal_handlers(
    logger: Any, *, timeout_seconds: float | None = None
) -> None:
    """Install SIGINT/SIGTERM handlers to drain the logger gracefully.

    Safe no-op on platforms without signal support (e.g., Windows for SIGTERM)
    or in non-main threads.
    """

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None

    def _handler(signum: int, _frame: Any) -> None:  # pragma: no cover
        _ = signum  # appease static analyzers
        try:
            to = timeout_seconds
            if to is None:
                try:
                    # Lazy import to avoid cycles
                    from .settings import Settings

                    to = float(Settings().core.shutdown_timeout_seconds)
                except Exception:
                    to = 3.0
            # Run drain with timeout depending on context
            if loop is not None and loop.is_running():

                async def _drain() -> None:
                    try:
                        await asyncio.wait_for(logger.stop_and_drain(), timeout=to)
                    except asyncio.TimeoutError:
                        warn(
                            "shutdown",
                            "drain timeout",
                            timeout=to,
                        )

                try:
                    loop.create_task(_drain())
                except Exception:
                    pass
            else:
                try:
                    asyncio.run(asyncio.wait_for(logger.stop_and_drain(), timeout=to))
                except Exception:
                    warn("shutdown", "drain timeout or error", timeout=to)
        except Exception:
            # Never raise from signal handlers
            return

    try:
        signal.signal(signal.SIGTERM, _handler)
    except Exception:  # pragma: no cover
        pass
    try:
        signal.signal(signal.SIGINT, _handler)
    except Exception:  # pragma: no cover
        pass


__all__ = ["install_signal_handlers"]
