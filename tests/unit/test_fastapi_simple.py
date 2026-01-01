"""
Simple tests for FastAPI integration module.
"""

from __future__ import annotations

import pytest


class TestFastAPIIntegration:
    """Tests for FastAPI integration module."""

    def test_get_router_returns_router(self) -> None:
        """Test get_router returns an APIRouter."""
        pytest.importorskip("fastapi")
        from fapilog.fastapi.integration import get_router

        router = get_router()
        from fastapi import APIRouter

        assert isinstance(router, APIRouter)

    def test_fastapi_module_available(self) -> None:
        """Test FastAPI module AVAILABLE flag."""
        pytest.importorskip("fastapi")
        from fapilog.fastapi import AVAILABLE

        assert AVAILABLE is True

    def test_router_has_plugins_tag(self) -> None:
        """Test router has plugins tag."""
        pytest.importorskip("fastapi")
        from fapilog.fastapi.integration import router

        assert "plugins" in router.tags
