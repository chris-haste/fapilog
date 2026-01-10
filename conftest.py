"""
Root pytest configuration.
"""

import pytest

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
