"""Pytest configuration for fapilog-audit tests."""

from collections.abc import AsyncIterator

import pytest

from fapilog_audit import audit


@pytest.fixture(autouse=True)
async def _reset_global_audit_trail() -> AsyncIterator[None]:
    """Reset all audit trail instances between tests."""
    # Reset global state before each test
    await audit.reset_all_audit_trails()
    yield
    # Cleanup after test
    await audit.reset_all_audit_trails()
