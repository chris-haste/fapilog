"""Tests for RuntimeInfoEnricher returning v1.1 schema structure."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from fapilog.plugins.enrichers import RuntimeInfoEnricher


@pytest.mark.asyncio
async def test_returns_diagnostics_structure() -> None:
    """RuntimeInfoEnricher returns nested structure targeting diagnostics group."""
    enricher = RuntimeInfoEnricher()
    await enricher.start()
    result = await enricher.enrich({})

    assert "diagnostics" in result
    assert isinstance(result["diagnostics"], dict)
    # Should not have flat top-level runtime fields
    assert "host" not in result
    assert "pid" not in result


@pytest.mark.asyncio
async def test_diagnostics_contains_host_pid_python() -> None:
    """Diagnostics group contains runtime info fields."""
    enricher = RuntimeInfoEnricher()
    await enricher.start()
    result = await enricher.enrich({})

    diag = result["diagnostics"]
    assert "host" in diag
    assert "pid" in diag
    assert "python" in diag
    assert isinstance(diag["pid"], int)


@pytest.mark.asyncio
async def test_diagnostics_includes_service_and_env_from_env_vars() -> None:
    """Service and env are included when environment variables are set."""
    with patch.dict(
        os.environ, {"FAPILOG_SERVICE": "myservice", "FAPILOG_ENV": "prod"}
    ):
        enricher = RuntimeInfoEnricher()
        await enricher.start()
        result = await enricher.enrich({})

    diag = result["diagnostics"]
    assert diag["service"] == "myservice"
    assert diag["env"] == "prod"


@pytest.mark.asyncio
async def test_diagnostics_excludes_none_values() -> None:
    """None values are not included in diagnostics (compact output)."""
    # Clear FAPILOG_VERSION to ensure it's None
    with patch.dict(os.environ, {}, clear=True):
        enricher = RuntimeInfoEnricher()
        await enricher.start()
        result = await enricher.enrich({})

    diag = result["diagnostics"]
    # version should not be present if env var not set
    assert "version" not in diag or diag.get("version") is not None


@pytest.mark.asyncio
async def test_diagnostics_includes_version_when_set() -> None:
    """Version is included when FAPILOG_VERSION is set."""
    with patch.dict(os.environ, {"FAPILOG_VERSION": "1.2.3"}, clear=False):
        enricher = RuntimeInfoEnricher()
        await enricher.start()
        result = await enricher.enrich({})

    diag = result["diagnostics"]
    assert diag["version"] == "1.2.3"
