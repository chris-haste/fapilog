from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fapilog.fastapi.integration import get_router


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(get_router())
    return app


def test_list_plugins_endpoint(app: FastAPI):
    client = TestClient(app)
    resp = client.get("/plugins")
    assert resp.status_code == 200
    data: Any = json.loads(resp.content)
    assert "total" in data and "items" in data


def test_search_plugins_endpoint(app: FastAPI):
    client = TestClient(app)
    resp = client.get(
        "/plugins/search",
        params={"query": "fastapi", "sort": "relevance"},
    )
    assert resp.status_code == 200
    data: Any = json.loads(resp.content)
    assert "total" in data and "items" in data
