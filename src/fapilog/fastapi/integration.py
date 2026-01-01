"""
FastAPI integration router.

Note: The plugin marketplace endpoints have been removed.
A simpler plugin configuration system is planned for a future release.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["plugins"])


def get_router() -> APIRouter:
    """Return the FastAPI router for plugin-related endpoints.

    Currently returns an empty router. Plugin marketplace endpoints
    have been removed in preparation for a simpler plugin system.
    """
    return router
