"""Pytest configuration for fapilog-audit tests."""

import pytest


@pytest.fixture(autouse=True)
def _reset_global_audit_trail():
    """Reset global audit trail between tests."""
    from fapilog_audit import audit

    # Reset global state before each test
    audit._audit_trail = None
    yield
    # Cleanup after test
    audit._audit_trail = None
