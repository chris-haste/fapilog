from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Iterable

from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from ..core.errors import request_id_var


class LoggingMiddleware(BaseHTTPMiddleware):
    """Request/response logging for FastAPI/Starlette apps.

    Logs a completion event with method, path, status, latency_ms, and correlation_id.
    Errors are logged with request_failed and re-raised for FastAPI to handle.
    """

    def __init__(
        self,
        app: Any,
        *,
        logger: Any | None = None,
        skip_paths: Iterable[str] | None = None,
        sample_rate: float = 1.0,
        include_headers: bool = False,
        redact_headers: Iterable[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._logger = logger
        self._skip_paths = set(skip_paths or [])
        self._logger_lock = asyncio.Lock()
        self._sample_rate = float(sample_rate)
        self._include_headers = bool(include_headers)
        self._redact_headers = {h.lower() for h in (redact_headers or [])}

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        if path in self._skip_paths:
            return await call_next(request)

        start = time.perf_counter()

        # Correlation: honor existing request_id_var, otherwise set from header or UUID
        token = None
        try:
            current = request_id_var.get(None)
        except Exception:  # pragma: no cover - best-effort correlation only
            current = None
        correlation_id = (
            current or request.headers.get("X-Request-ID") or str(uuid.uuid4())
        )
        try:
            token = request_id_var.set(correlation_id)
        except Exception:  # pragma: no cover - best-effort correlation only
            token = None

        try:
            response = await call_next(request)
            await self._log_completion(
                request=request,
                status_code=response.status_code,
                correlation_id=correlation_id,
                latency_ms=(time.perf_counter() - start) * 1000.0,
            )
            response.headers.setdefault("X-Request-ID", correlation_id)
            return response
        except Exception as exc:  # pragma: no cover - diagnostics only
            status_code = 500
            if isinstance(exc, HTTPException):
                status_code = exc.status_code
            await self._log_error(
                request=request,
                status_code=status_code,
                correlation_id=correlation_id,
                latency_ms=(time.perf_counter() - start) * 1000.0,
                exc=exc,
            )
            raise
        finally:
            if token is not None:
                try:
                    request_id_var.reset(token)
                except Exception:  # pragma: no cover - best-effort reset
                    pass

    async def _get_logger(self) -> Any:
        if self._logger is not None:
            return self._logger
        async with self._logger_lock:
            if self._logger is None:
                from .. import get_async_logger

                self._logger = await get_async_logger("fastapi")
        return self._logger

    async def _log_completion(
        self,
        *,
        request: Request,
        status_code: int,
        correlation_id: str,
        latency_ms: float,
    ) -> None:
        # Sampling applies only to successful completion logs
        if self._sample_rate < 1.0:
            try:
                import random

                if random.random() > self._sample_rate:
                    return
            except Exception:
                # If sampling fails, proceed to log
                pass
        try:
            logger = await self._get_logger()
            headers: dict[str, str] | None = None
            if self._include_headers:
                headers = {}
                for key, value in request.headers.items():
                    lk = key.lower()
                    if lk in self._redact_headers:
                        headers[lk] = "***"
                    else:
                        headers[lk] = value
            await logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                latency_ms=round(latency_ms, 3),
                correlation_id=correlation_id,
                client_ip=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                headers=headers,
            )
        except Exception:  # pragma: no cover - diagnostics only
            # Diagnostics best-effort
            try:
                from ..core import diagnostics as _diag

                _diag.warn(
                    "fastapi",
                    "failed to log request completion",
                    path=request.url.path,
                )
            except Exception:  # pragma: no cover - diagnostics only
                pass

    async def _log_error(
        self,
        *,
        request: Request,
        status_code: int,
        correlation_id: str,
        latency_ms: float,
        exc: Exception,
    ) -> None:
        try:
            logger = await self._get_logger()
            await logger.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                latency_ms=round(latency_ms, 3),
                correlation_id=correlation_id,
                error_type=type(exc).__name__,
                error=str(exc),
            )
        except Exception:  # pragma: no cover - diagnostics only
            try:
                from ..core import diagnostics as _diag

                _diag.warn(
                    "fastapi",
                    "failed to log request error",
                    path=request.url.path,
                )
            except Exception:
                pass


__all__ = ["LoggingMiddleware"]
