"""
Root pytest configuration.
"""

import os

import pytest


def get_test_timeout(base: float, max_multiplier: float = 5.0) -> float:
    """Apply CI timeout multiplier to a base timeout value.

    Args:
        base: Base timeout in seconds
        max_multiplier: Maximum allowed multiplier (default 5x)

    Returns:
        Scaled timeout value

    Environment:
        CI_TIMEOUT_MULTIPLIER: Multiplier for CI environments (default: 1.0)

    Note:
        Reads env var on each call to support per-test monkeypatching.
    """
    raw = os.getenv("CI_TIMEOUT_MULTIPLIER", "1.0")
    try:
        multiplier = float(raw) if raw else 1.0
        multiplier = min(multiplier, max_multiplier)
    except ValueError:
        multiplier = 1.0
    return base * multiplier


# Register fapilog testing fixtures for all tests
pytest_plugins = ("fapilog.testing.fixtures",)


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for test categorization."""
    config.addinivalue_line(
        "markers",
        "critical: Tests that must never fail - core functionality",
    )
    config.addinivalue_line(
        "markers",
        "security: Security-critical tests (redaction, auth, secrets)",
    )
    config.addinivalue_line(
        "markers",
        "standard: Default risk category for typical unit tests",
    )
    config.addinivalue_line(
        "markers",
        "integration: Tests requiring external dependencies",
    )
    config.addinivalue_line(
        "markers",
        "slow: Tests that take >1 second",
    )
    config.addinivalue_line(
        "markers",
        "flaky: Tests with known intermittent failures (tracked for fixing)",
    )
    config.addinivalue_line(
        "markers",
        "asyncio: Async tests",
    )
    config.addinivalue_line(
        "markers",
        "postgres: Tests requiring PostgreSQL",
    )
    config.addinivalue_line(
        "markers",
        "property: Property-based tests (may be slow)",
    )
    config.addinivalue_line(
        "markers",
        "benchmark: Benchmark tests",
    )
    config.addinivalue_line(
        "markers",
        "enterprise: Enterprise feature tests",
    )
