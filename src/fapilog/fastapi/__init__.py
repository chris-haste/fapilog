from __future__ import annotations

# Import guard: FastAPI integration is optional and provided via the
# `fapilog[fastapi]` extra. If FastAPI is not installed, we expose
# AVAILABLE = False and capture the import error for diagnostics.

AVAILABLE: bool
_IMPORT_ERROR: Exception | None

try:
    from .context import RequestContextMiddleware
    from .dependencies import get_request_logger
    from .integration import get_router  # re-export primary API
    from .logging import LoggingMiddleware
    from .setup import setup_logging

    AVAILABLE = True
    _IMPORT_ERROR = None
except Exception as e:  # pragma: no cover - exercised in envs without extra
    AVAILABLE = False
    _IMPORT_ERROR = e

__all__ = [
    "AVAILABLE",
    "get_request_logger",
    "get_router",
    "LoggingMiddleware",
    "RequestContextMiddleware",
    "setup_logging",
]
