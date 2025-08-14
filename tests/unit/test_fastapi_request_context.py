from __future__ import annotations

import json

from fastapi import FastAPI
from starlette.testclient import TestClient

from fapilog.core.errors import (
    request_id_var,
    span_id_var,
    tenant_id_var,
    trace_id_var,
    user_id_var,
)
from fapilog.fastapi.context import (
    RequestContextMiddleware,
    _parse_traceparent,
)


def test_parse_traceparent_valid_and_invalid() -> None:
    valid = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    t, s = _parse_traceparent(valid)
    assert t == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert s == "00f067aa0ba902b7"
    bad = "garbage"
    t2, s2 = _parse_traceparent(bad)
    assert t2 is None and s2 is None


def test_middleware_sets_contextvars_and_header_roundtrip() -> None:
    app = FastAPI()

    @app.get("/ctx")
    def ctx() -> dict[str, str | None]:
        # Read directly from ContextVars to verify propagation
        try:
            rid = request_id_var.get(None)
        except Exception:
            rid = None
        try:
            uid = user_id_var.get(None)
        except Exception:
            uid = None
        try:
            tid = tenant_id_var.get(None)
        except Exception:
            tid = None
        try:
            tr = trace_id_var.get(None)
        except Exception:
            tr = None
        try:
            sp = span_id_var.get(None)
        except Exception:
            sp = None
        return {
            "request_id": rid,
            "user_id": uid,
            "tenant_id": tid,
            "trace_id": tr,
            "span_id": sp,
        }

    app.add_middleware(RequestContextMiddleware)
    client = TestClient(app)
    headers = {
        "X-Request-ID": "req-1",
        "X-User-ID": "u-1",
        "X-Tenant-ID": "t-1",
        "traceparent": ("00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"),
    }
    resp = client.get("/ctx", headers=headers)
    assert resp.status_code == 200
    data = json.loads(resp.content)
    assert data["request_id"] == "req-1"
    assert data["user_id"] == "u-1"
    assert data["tenant_id"] == "t-1"
    assert data["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert data["span_id"] == "00f067aa0ba902b7"
    # Response should echo correlation id
    assert resp.headers.get("X-Request-ID") == "req-1"
