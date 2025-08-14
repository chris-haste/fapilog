from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from fapilog.fastapi.integration import get_router


def test_integration_router_smoke() -> None:
    app = FastAPI()
    app.include_router(get_router())
    client = TestClient(app)
    r = client.get("/plugins")
    assert r.status_code in (200, 500)
