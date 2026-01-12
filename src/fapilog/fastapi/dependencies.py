from __future__ import annotations

from typing import Any

try:
    from fastapi import Request
except Exception:  # pragma: no cover - optional dependency
    Request = None  # type: ignore


async def get_request_logger(request: Request = None) -> Any:  # type: ignore[assignment]
    """FastAPI dependency that provides request-scoped logger.

    Prefers the logger created by setup_logging (app.state.fapilog_logger) and
    falls back to get_async_logger("fastapi") when unavailable.
    """
    if request is not None:
        try:
            logger = request.app.state.fapilog_logger
        except Exception:
            logger = None
        if logger is not None:
            return logger

    from .. import get_async_logger

    return await get_async_logger("fastapi")


__all__ = ["get_request_logger"]
