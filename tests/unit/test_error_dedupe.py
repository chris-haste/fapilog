"""Tests for error deduplication bounded memory (Story 1.55)."""

from __future__ import annotations

from collections import OrderedDict
from unittest.mock import patch

import pytest


class TestErrorDedupeSettings:
    """AC5: Configurable cap and TTL with sensible defaults."""

    def test_default_max_entries(self) -> None:
        from fapilog.core.settings import CoreSettings

        settings = CoreSettings()
        assert settings.error_dedupe_max_entries == 1000

    def test_default_ttl_multiplier(self) -> None:
        from fapilog.core.settings import CoreSettings

        settings = CoreSettings()
        assert settings.error_dedupe_ttl_multiplier == 10.0

    def test_custom_max_entries(self) -> None:
        from fapilog.core.settings import CoreSettings

        settings = CoreSettings(error_dedupe_max_entries=500)
        assert settings.error_dedupe_max_entries == 500

    def test_custom_ttl_multiplier(self) -> None:
        from fapilog.core.settings import CoreSettings

        settings = CoreSettings(error_dedupe_ttl_multiplier=5.0)
        assert settings.error_dedupe_ttl_multiplier == 5.0

    def test_max_entries_must_be_positive(self) -> None:
        from pydantic import ValidationError

        from fapilog.core.settings import CoreSettings

        with pytest.raises(ValidationError, match="error_dedupe_max_entries"):
            CoreSettings(error_dedupe_max_entries=0)


class TestErrorDedupeBoundedMemory:
    """AC1, AC2: Dict size is bounded, oldest entries evicted first."""

    @pytest.fixture()
    def logger(self):
        """Create a minimal logger for dedupe testing."""
        from fapilog.core.logger import SyncLoggerFacade

        facade = SyncLoggerFacade(
            name="test",
            queue_capacity=100,
            batch_max_size=10,
            batch_timeout_seconds=1.0,
            backpressure_wait_ms=0,
            drop_on_full=True,
            sink_write=lambda batch: None,
            protected_levels=[],
        )
        facade._cached_error_dedupe_window = 5.0
        facade._cached_error_dedupe_max_entries = 10
        facade._cached_error_dedupe_ttl_multiplier = 10.0
        return facade

    def test_dict_never_exceeds_max_entries(self, logger) -> None:
        """AC1: _error_dedupe never exceeds error_dedupe_max_entries."""
        with patch("time.monotonic", side_effect=[float(i) for i in range(30)]):
            # Each message is unique, window is 5s, new timestamp each time
            for i in range(20):
                logger._prepare_payload("ERROR", f"unique-error-{i}")

        assert len(logger._error_dedupe) <= 10

    def test_oldest_entry_evicted_first(self, logger) -> None:
        """AC2: When cap is reached, oldest first-seen entry is removed."""
        # Insert messages 0-9 (fills cap)
        timestamps = list(range(20))
        with patch("time.monotonic", side_effect=[float(t) for t in timestamps]):
            for i in range(10):
                logger._prepare_payload("ERROR", f"unique-error-{i}")

            # Add one more — message 0 should be evicted
            logger._prepare_payload("ERROR", "unique-error-10")

        assert "unique-error-0" not in logger._error_dedupe
        assert "unique-error-10" in logger._error_dedupe

    def test_dict_uses_ordered_dict(self, logger) -> None:
        """Implementation uses OrderedDict for FIFO eviction."""
        assert isinstance(logger._error_dedupe, OrderedDict)


class TestErrorDedupeTTLSweep:
    """AC3: TTL sweep prunes stale entries."""

    @pytest.fixture()
    def logger(self):
        from fapilog.core.logger import SyncLoggerFacade

        facade = SyncLoggerFacade(
            name="test",
            queue_capacity=100,
            batch_max_size=10,
            batch_timeout_seconds=1.0,
            backpressure_wait_ms=0,
            drop_on_full=True,
            sink_write=lambda batch: None,
            protected_levels=[],
        )
        facade._cached_error_dedupe_window = 5.0
        facade._cached_error_dedupe_max_entries = 1000
        facade._cached_error_dedupe_ttl_multiplier = 10.0
        return facade

    def test_ttl_sweep_prunes_stale_entries(self, logger) -> None:
        """AC3: Entries older than window * ttl_multiplier are pruned."""
        # TTL = 5.0 * 10.0 = 50s
        # Insert entry at t=0
        with patch("time.monotonic", return_value=0.0):
            logger._prepare_payload("ERROR", "old-error")

        assert "old-error" in logger._error_dedupe

        # Simulate 99 checks to get to sweep point (check_count starts at 0)
        # Then at check 100, sweep should fire
        # At t=60 the entry is 60s old, TTL is 50s → should be pruned
        logger._dedupe_check_count = 99
        with patch("time.monotonic", return_value=60.0):
            logger._prepare_payload("ERROR", "trigger-sweep")

        assert "old-error" not in logger._error_dedupe

    def test_ttl_sweep_keeps_fresh_entries(self, logger) -> None:
        """TTL sweep does not prune entries within TTL."""
        # TTL = 50s. Insert at t=0, sweep at t=30 — entry is only 30s old
        with patch("time.monotonic", return_value=0.0):
            logger._prepare_payload("ERROR", "fresh-error")

        logger._dedupe_check_count = 99
        with patch("time.monotonic", return_value=30.0):
            logger._prepare_payload("ERROR", "trigger-sweep")

        assert "fresh-error" in logger._error_dedupe

    def test_sweep_counter_resets_after_sweep(self, logger) -> None:
        """Counter resets to 0 after a sweep."""
        logger._dedupe_check_count = 99
        with patch("time.monotonic", return_value=0.0):
            logger._prepare_payload("ERROR", "msg")

        assert logger._dedupe_check_count == 0


class TestErrorDedupeActiveWindow:
    """AC4: Active deduplication behavior unchanged."""

    @pytest.fixture()
    def logger(self):
        from fapilog.core.logger import SyncLoggerFacade

        facade = SyncLoggerFacade(
            name="test",
            queue_capacity=100,
            batch_max_size=10,
            batch_timeout_seconds=1.0,
            backpressure_wait_ms=0,
            drop_on_full=True,
            sink_write=lambda batch: None,
            protected_levels=[],
        )
        facade._cached_error_dedupe_window = 5.0
        facade._cached_error_dedupe_max_entries = 1000
        facade._cached_error_dedupe_ttl_multiplier = 10.0
        return facade

    def test_duplicate_suppressed_within_window(self, logger) -> None:
        """AC4: Same message within window is suppressed."""
        with patch("time.monotonic", return_value=1.0):
            result1 = logger._prepare_payload("ERROR", "same-message")
            result2 = logger._prepare_payload("ERROR", "same-message")

        assert result1 is not None  # First occurrence passes  # noqa: WA003
        assert result2 is None  # Duplicate suppressed

    def test_refreshed_entry_moves_to_end(self, logger) -> None:
        """Refreshed entry (window expired) is moved to end of OrderedDict."""
        # Insert msg-a at t=0, msg-b at t=1
        with patch("time.monotonic", return_value=0.0):
            logger._prepare_payload("ERROR", "msg-a")
        with patch("time.monotonic", return_value=1.0):
            logger._prepare_payload("ERROR", "msg-b")

        # Refresh msg-a at t=10 (window=5s expired)
        with patch("time.monotonic", return_value=10.0):
            logger._prepare_payload("ERROR", "msg-a")

        # msg-a should now be at the end (most recent)
        keys = list(logger._error_dedupe.keys())
        assert keys[-1] == "msg-a"
        assert keys[0] == "msg-b"


class TestErrorDedupeDisabled:
    """AC6: Zero overhead when deduplication is disabled."""

    def test_no_cap_logic_when_disabled(self) -> None:
        """When window=0, no dedupe dict entries are created."""
        from fapilog.core.logger import SyncLoggerFacade

        facade = SyncLoggerFacade(
            name="test",
            queue_capacity=100,
            batch_max_size=10,
            batch_timeout_seconds=1.0,
            backpressure_wait_ms=0,
            drop_on_full=True,
            sink_write=lambda batch: None,
            protected_levels=[],
        )
        facade._cached_error_dedupe_window = 0.0

        facade._prepare_payload("ERROR", "some-error")

        assert len(facade._error_dedupe) == 0


class TestErrorDedupeContract:
    """AC7: Contract test — deduplication round-trip."""

    def test_new_message_after_eviction_produces_envelope(self) -> None:
        """Messages after eviction still produce valid envelopes."""
        from fapilog.core.logger import SyncLoggerFacade

        facade = SyncLoggerFacade(
            name="test",
            queue_capacity=100,
            batch_max_size=10,
            batch_timeout_seconds=1.0,
            backpressure_wait_ms=0,
            drop_on_full=True,
            sink_write=lambda batch: None,
            protected_levels=[],
        )
        facade._cached_error_dedupe_window = 5.0
        facade._cached_error_dedupe_max_entries = 5
        facade._cached_error_dedupe_ttl_multiplier = 10.0

        # Fill and overflow the cap
        timestamps = list(range(20))
        with patch("time.monotonic", side_effect=[float(t) for t in timestamps]):
            for i in range(7):
                facade._prepare_payload("ERROR", f"error-{i}")

            # New message after eviction should produce a valid envelope
            result = facade._prepare_payload("ERROR", "new-after-eviction")

        assert result is not None  # noqa: WA003
        assert result["message"] == "new-after-eviction"
        assert result["level"] == "ERROR"
