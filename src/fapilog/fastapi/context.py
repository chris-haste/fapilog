from __future__ import annotations

import re
import uuid
from typing import Awaitable, Callable  # noqa: F401

from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import Response

from ..core.errors import (
    request_id_var,
    span_id_var,
    tenant_id_var,
    trace_id_var,
    user_id_var,
)

_TRACEPARENT_RE = re.compile(
    r"^(?P<version>[0-9a-fA-F]{2})-(?P<trace_id>[0-9a-fA-F]{32})-"
    r"(?P<span_id>[0-9a-fA-F]{16})-(?P<trace_flags>[0-9a-fA-F]{2})$"
)


def _parse_traceparent(value: str) -> tuple[str | None, str | None]:
    m = _TRACEPARENT_RE.match(value.strip())
    if not m:
        return None, None
    return m.group("trace_id"), m.group("span_id")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Extract headers
        hdr_request_id = request.headers.get("X-Request-ID")
        hdr_user_id = request.headers.get("X-User-ID")
        hdr_tenant_id = request.headers.get("X-Tenant-ID")
        hdr_traceparent = request.headers.get("traceparent")

        # Set contextvars; keep tokens to reset later
        tok_request_id = tok_user_id = tok_tenant_id = None
        tok_trace_id = tok_span_id = None

        try:
            rid = hdr_request_id or str(uuid.uuid4())
            tok_request_id = request_id_var.set(rid)
            if hdr_user_id:
                tok_user_id = user_id_var.set(hdr_user_id)
            if hdr_tenant_id:
                tok_tenant_id = tenant_id_var.set(hdr_tenant_id)
            if hdr_traceparent:
                t_id, s_id = _parse_traceparent(hdr_traceparent)
                if t_id:
                    tok_trace_id = trace_id_var.set(t_id)
                if s_id:
                    tok_span_id = span_id_var.set(s_id)
            response = await call_next(request)
            # Reflect correlation header in response for clients
            response.headers.setdefault("X-Request-ID", rid)
            return response
        finally:
            if tok_trace_id:
                trace_id_var.reset(tok_trace_id)
            if tok_span_id:
                span_id_var.reset(tok_span_id)
            if tok_tenant_id:
                tenant_id_var.reset(tok_tenant_id)
            if tok_user_id:
                user_id_var.reset(tok_user_id)
            if tok_request_id:
                request_id_var.reset(tok_request_id)


__all__ = ["RequestContextMiddleware", "_parse_traceparent"]

# Hint for static analyzers: Starlette calls the middleware
# dispatch method via BaseHTTPMiddleware.
_ = RequestContextMiddleware.dispatch
