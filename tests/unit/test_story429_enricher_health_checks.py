"""
Health check tests for enricher plugins.

Story 4.29: Plugin Consistency and Completeness
"""

from __future__ import annotations

import pytest

from fapilog.plugins.enrichers.context_vars import ContextVarsEnricher
from fapilog.plugins.enrichers.runtime_info import RuntimeInfoEnricher


@pytest.mark.asyncio
async def test_runtime_info_enricher_health_check() -> None:
    """RuntimeInfoEnricher health check should return True when healthy."""
    enricher = RuntimeInfoEnricher()
    result = await enricher.health_check()
    assert result is True


@pytest.mark.asyncio
async def test_runtime_info_enricher_has_health_check_method() -> None:
    """RuntimeInfoEnricher should have health_check method defined."""
    enricher = RuntimeInfoEnricher()
    assert hasattr(enricher, "health_check")
    assert callable(enricher.health_check)


@pytest.mark.asyncio
async def test_context_vars_enricher_health_check() -> None:
    """ContextVarsEnricher health check should return True when healthy."""
    enricher = ContextVarsEnricher()
    result = await enricher.health_check()
    assert result is True


@pytest.mark.asyncio
async def test_context_vars_enricher_has_health_check_method() -> None:
    """ContextVarsEnricher should have health_check method defined."""
    enricher = ContextVarsEnricher()
    assert hasattr(enricher, "health_check")
    assert callable(enricher.health_check)
