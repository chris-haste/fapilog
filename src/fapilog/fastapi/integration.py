"""
FastAPI integration router.

Provides plugin-related endpoints for the FastAPI integration.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["plugins"])


def get_router() -> APIRouter:
    """Return the FastAPI router for plugin-related endpoints."""
    return router
