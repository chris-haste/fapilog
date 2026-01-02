"""
Health check tests for processor plugins.

Story 4.29: Plugin Consistency and Completeness
"""

from __future__ import annotations

import pytest

from fapilog.plugins.processors.zero_copy import ZeroCopyProcessor


@pytest.mark.asyncio
async def test_zero_copy_processor_health_check() -> None:
    """ZeroCopyProcessor health check should return True when healthy."""
    processor = ZeroCopyProcessor()
    result = await processor.health_check()
    assert result is True


@pytest.mark.asyncio
async def test_zero_copy_processor_has_health_check_method() -> None:
    """ZeroCopyProcessor should have health_check method defined."""
    processor = ZeroCopyProcessor()
    assert hasattr(processor, "health_check")
    assert callable(processor.health_check)


@pytest.mark.asyncio
async def test_zero_copy_processor_health_check_after_processing() -> None:
    """ZeroCopyProcessor health check should return True after processing."""
    processor = ZeroCopyProcessor()

    # Process some data
    data = b'{"message": "test"}'
    view = memoryview(data)
    await processor.process(view)

    # Health check should still pass
    result = await processor.health_check()
    assert result is True
