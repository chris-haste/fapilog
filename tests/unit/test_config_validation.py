"""Tests for logger configuration validation."""

from __future__ import annotations

import pytest

from fapilog.core.logger import AsyncLoggerFacade, SyncLoggerFacade, _LoggerMixin


async def noop_sink(entry: dict) -> None:
    """No-op sink for testing."""
    pass


def make_logger(**overrides):
    """Create a SyncLoggerFacade with default valid config, allowing overrides."""
    defaults = {
        "name": "test",
        "queue_capacity": 100,
        "batch_max_size": 10,
        "batch_timeout_seconds": 0.1,
        "backpressure_wait_ms": 5,
        "drop_on_full": True,
        "sink_write": noop_sink,
        "enrichers": [],
        "metrics": None,
    }
    defaults.update(overrides)
    return SyncLoggerFacade(**defaults)


class TestConfigValidationLimits:
    """Test that validation limits are defined correctly."""

    def test_warn_limits_are_defined(self) -> None:
        """Verify warning thresholds are set to reasonable values."""
        assert _LoggerMixin._WARN_NUM_WORKERS == 32
        assert _LoggerMixin._WARN_QUEUE_CAPACITY == 1_000_000
        assert _LoggerMixin._WARN_BATCH_MAX_SIZE == 10_000


class TestConfigValidationMinimums:
    """Test that minimum values are enforced."""

    def test_queue_capacity_zero_rejected(self) -> None:
        """queue_capacity=0 raises ValueError."""
        with pytest.raises(ValueError, match="queue_capacity must be at least 1"):
            make_logger(queue_capacity=0)

    def test_queue_capacity_negative_rejected(self) -> None:
        """Negative queue_capacity raises ValueError."""
        with pytest.raises(ValueError, match="queue_capacity must be at least 1"):
            make_logger(queue_capacity=-1)

    def test_batch_max_size_zero_rejected(self) -> None:
        """batch_max_size=0 raises ValueError."""
        with pytest.raises(ValueError, match="batch_max_size must be at least 1"):
            make_logger(batch_max_size=0)

    def test_batch_max_size_negative_rejected(self) -> None:
        """Negative batch_max_size raises ValueError."""
        with pytest.raises(ValueError, match="batch_max_size must be at least 1"):
            make_logger(batch_max_size=-1)

    def test_batch_timeout_zero_rejected(self) -> None:
        """batch_timeout_seconds=0 raises ValueError."""
        with pytest.raises(ValueError, match="batch_timeout_seconds must be positive"):
            make_logger(batch_timeout_seconds=0)

    def test_batch_timeout_negative_rejected(self) -> None:
        """Negative batch_timeout_seconds raises ValueError."""
        with pytest.raises(ValueError, match="batch_timeout_seconds must be positive"):
            make_logger(batch_timeout_seconds=-1)

    def test_num_workers_zero_rejected(self) -> None:
        """num_workers=0 raises ValueError."""
        with pytest.raises(ValueError, match="num_workers must be at least 1"):
            make_logger(num_workers=0)

    def test_num_workers_negative_rejected(self) -> None:
        """Negative num_workers raises ValueError."""
        with pytest.raises(ValueError, match="num_workers must be at least 1"):
            make_logger(num_workers=-1)


class TestConfigValidationValidValues:
    """Test that valid configurations are accepted."""

    def test_minimum_valid_values_accepted(self) -> None:
        """Minimum valid values (all 1s) are accepted."""
        logger = make_logger(
            queue_capacity=1,
            batch_max_size=1,
            batch_timeout_seconds=0.001,
            num_workers=1,
        )
        assert logger._queue._capacity == 1
        assert logger._batch_max_size == 1
        assert logger._num_workers == 1

    def test_moderate_values_accepted(self) -> None:
        """Moderate values within recommended range are accepted."""
        logger = make_logger(
            queue_capacity=10_000,
            batch_max_size=500,
            batch_timeout_seconds=1.0,
            num_workers=8,
        )
        assert logger._queue._capacity == 10_000
        assert logger._batch_max_size == 500
        assert logger._num_workers == 8

    def test_at_warning_threshold_accepted(self) -> None:
        """Values at the warning threshold are accepted (warnings emitted separately)."""
        logger = make_logger(
            queue_capacity=_LoggerMixin._WARN_QUEUE_CAPACITY,
            batch_max_size=_LoggerMixin._WARN_BATCH_MAX_SIZE,
            num_workers=_LoggerMixin._WARN_NUM_WORKERS,
        )
        assert logger._queue._capacity == _LoggerMixin._WARN_QUEUE_CAPACITY
        assert logger._batch_max_size == _LoggerMixin._WARN_BATCH_MAX_SIZE
        assert logger._num_workers == _LoggerMixin._WARN_NUM_WORKERS

    def test_above_warning_threshold_accepted(self) -> None:
        """Values above warning threshold are accepted (soft limit, not hard)."""
        # This should work but emit warnings via diagnostics
        logger = make_logger(
            queue_capacity=_LoggerMixin._WARN_QUEUE_CAPACITY + 1,
            batch_max_size=_LoggerMixin._WARN_BATCH_MAX_SIZE + 1,
            num_workers=_LoggerMixin._WARN_NUM_WORKERS + 1,
        )
        assert logger._queue._capacity == _LoggerMixin._WARN_QUEUE_CAPACITY + 1
        assert logger._batch_max_size == _LoggerMixin._WARN_BATCH_MAX_SIZE + 1
        assert logger._num_workers == _LoggerMixin._WARN_NUM_WORKERS + 1


class TestConfigValidationBatchQueueRelationship:
    """Test validation of batch_max_size vs queue_capacity relationship."""

    def test_batch_size_less_than_queue_accepted(self) -> None:
        """batch_max_size < queue_capacity is normal and accepted."""
        logger = make_logger(queue_capacity=100, batch_max_size=10)
        assert logger._batch_max_size == 10
        assert logger._queue._capacity == 100

    def test_batch_size_equal_to_queue_accepted(self) -> None:
        """batch_max_size == queue_capacity is accepted."""
        logger = make_logger(queue_capacity=100, batch_max_size=100)
        assert logger._batch_max_size == 100
        assert logger._queue._capacity == 100

    def test_batch_size_greater_than_queue_accepted_with_warning(self) -> None:
        """batch_max_size > queue_capacity is accepted but warns.

        This configuration is suboptimal (batches can never reach max size)
        but not invalid.
        """
        logger = make_logger(queue_capacity=50, batch_max_size=100)
        assert logger._batch_max_size == 100
        assert logger._queue._capacity == 50


class TestAsyncLoggerFacadeValidation:
    """Test that AsyncLoggerFacade also validates configuration."""

    def test_async_facade_validates_queue_capacity(self) -> None:
        """AsyncLoggerFacade rejects invalid queue_capacity."""
        with pytest.raises(ValueError, match="queue_capacity must be at least 1"):
            AsyncLoggerFacade(
                name="test",
                queue_capacity=0,
                batch_max_size=10,
                batch_timeout_seconds=0.1,
                backpressure_wait_ms=5,
                drop_on_full=True,
                sink_write=noop_sink,
                enrichers=[],
                metrics=None,
            )

    def test_async_facade_validates_num_workers(self) -> None:
        """AsyncLoggerFacade rejects invalid num_workers."""
        with pytest.raises(ValueError, match="num_workers must be at least 1"):
            AsyncLoggerFacade(
                name="test",
                queue_capacity=100,
                batch_max_size=10,
                batch_timeout_seconds=0.1,
                backpressure_wait_ms=5,
                drop_on_full=True,
                sink_write=noop_sink,
                enrichers=[],
                metrics=None,
                num_workers=0,
            )
