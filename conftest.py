"""
Root pytest configuration.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator, Generator

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
    config.addinivalue_line(
        "markers",
        "contract: Contract tests ensuring schema compatibility between pipeline stages",
    )


@pytest.fixture(autouse=True)
def reset_diagnostics_cache() -> Generator[None, None, None]:
    """Reset the diagnostics module cache before each test.

    The diagnostics module caches the `internal_logging_enabled` setting
    at first access (Story 1.25). This fixture ensures test isolation by
    resetting the cache to None before each test, so tests don't inherit
    cached state from previous tests.
    """
    import fapilog.core.diagnostics as diag

    # Reset the cache to None so each test can set it as needed
    diag._internal_logging_enabled = None
    yield
    # Also reset after test to clean up
    diag._internal_logging_enabled = None


@pytest.fixture(autouse=True)
async def _clear_logger_cache() -> AsyncGenerator[None, None]:
    """Clear logger cache before and after each test.

    Story 10.29 introduced logger caching by default, which requires
    this cleanup to maintain test isolation - each test gets fresh
    logger instances rather than potentially reusing cached loggers.
    """
    from fapilog import clear_logger_cache

    await clear_logger_cache()
    yield
    await clear_logger_cache()


@pytest.fixture
def strict_serialization(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    """Fail if fallback serialization is triggered.

    Use this fixture in tests where the happy path should always work.
    If fallback triggers, it indicates schema drift between build_envelope()
    and serialize_envelope().

    The fallback path in LoggerWorker._try_serialize() calls
    serialize_mapping_to_json_bytes() when serialize_envelope() fails.
    This fixture monkeypatches that fallback to fail loudly.

    Example:
        def test_normal_logging_uses_envelope_path(strict_serialization, logger):
            '''Normal logging should never trigger fallback.'''
            logger.info("test message")
            # If fallback is triggered, test fails with clear message

    See Story 10.17 for context on contract testing infrastructure.
    """

    def _fail_on_fallback(*args: object, **kwargs: object) -> None:
        pytest.fail(
            "Fallback serialization triggered! "
            "This indicates schema mismatch between build_envelope() and serialize_envelope(). "
            "See Story 10.17 for context."
        )

    monkeypatch.setattr(
        "fapilog.core.worker.serialize_mapping_to_json_bytes",
        _fail_on_fallback,
    )
    yield
