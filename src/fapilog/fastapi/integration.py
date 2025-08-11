"""
FastAPI integration for marketplace discovery and search.

Endpoints:
- GET /plugins: list plugins (paginated)
- GET /plugins/search: full-text search with filters/sort

Static-first behavior: attempts to load a prebuilt JSON index from disk.
If not present, builds an offline index using installed packages and local
pyproject extras (no network calls).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Query

from fapilog.plugins.marketplace import (
    MarketplaceIndex,
    MarketplaceIndexBuilder,
    SearchFilters,
    SearchResult,
    deserialize_index_from_json_bytes,
    search_plugins,
    serialize_index_to_json_bytes,
)

router = APIRouter(tags=["plugins"])


def _load_or_build_index() -> MarketplaceIndex:
    index_path = Path(os.getenv("FAPILOG_PLUGINS_INDEX_PATH", "plugins.index.json"))
    if index_path.exists():
        data = index_path.read_bytes()
        return deserialize_index_from_json_bytes(data)

    builder = MarketplaceIndexBuilder()
    index = builder.build_index()

    # Best-effort write to disk for reuse in dev environments
    try:
        Path(index_path).write_bytes(serialize_index_to_json_bytes(index))
    except Exception:
        pass
    return index


async def get_index() -> MarketplaceIndex:
    # simple dependency wrapper for test overriding
    return _load_or_build_index()


@router.get("/plugins", response_model=SearchResult)
async def list_plugins(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=200),
    sort: str = Query(
        "relevance",
        pattern="^(relevance|downloads|last_updated)$",
    ),
    index: MarketplaceIndex = Depends(get_index),
) -> SearchResult:
    # cast to literal accepted by search function
    sort_literal: Literal["relevance", "downloads", "last_updated"] = (
        "downloads"
        if sort == "downloads"
        else "last_updated"
        if sort == "last_updated"
        else "relevance"
    )
    return search_plugins(
        index,
        sort=sort_literal,
        page=page,
        per_page=per_page,
    )


@router.get("/plugins/search", response_model=SearchResult)
async def search_plugins_endpoint(
    q: str | None = Query(None, alias="query"),
    type: str | None = Query(
        None, pattern="^(sink|processor|enricher|alerting|integration)$"
    ),
    distribution_type: str | None = Query(None, pattern="^(extra|package)$"),
    license: str | None = Query(None),
    supported_python: str | None = Query(None),
    supported_fapilog: str | None = Query(None),
    last_updated_from: str | None = Query(None),
    last_updated_to: str | None = Query(None),
    sort: str = Query(
        "relevance",
        pattern="^(relevance|downloads|last_updated)$",
    ),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=200),
    index: MarketplaceIndex = Depends(get_index),
) -> SearchResult:
    filters = SearchFilters(
        type=type,
        distribution_type=distribution_type,
        license=license,
        supported_python=supported_python,
        supported_fapilog=supported_fapilog,
        last_updated_from=last_updated_from,
        last_updated_to=last_updated_to,
    )
    sort_literal: Literal["relevance", "downloads", "last_updated"] = (
        "downloads"
        if sort == "downloads"
        else "last_updated"
        if sort == "last_updated"
        else "relevance"
    )
    return search_plugins(
        index,
        query=q,
        filters=filters,
        sort=sort_literal,
        page=page,
        per_page=per_page,
    )


def get_router() -> APIRouter:
    return router
