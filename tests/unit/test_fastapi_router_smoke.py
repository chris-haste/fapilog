from __future__ import annotations

from fastapi import APIRouter

from fapilog.fastapi.integration import get_router


def test_get_router_returns_apirouter() -> None:
    router = get_router()
    assert isinstance(router, APIRouter)
