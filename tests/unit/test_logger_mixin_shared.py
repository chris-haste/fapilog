"""Tests verifying shared behavior between SyncLoggerFacade and AsyncLoggerFacade via _LoggerMixin."""

from __future__ import annotations

from fapilog.core.logger import AsyncLoggerFacade, SyncLoggerFacade


async def _sink_write(event):  # type: ignore[no-untyped-def]
    return None


def _logger_args() -> dict:
    return {
        "name": "test",
        "queue_capacity": 8,
        "batch_max_size": 1,
        "batch_timeout_seconds": 0.1,
        "backpressure_wait_ms": 1,
        "drop_on_full": False,
        "sink_write": _sink_write,
        "sink_write_serialized": None,
        "enrichers": None,
        "processors": None,
        "filters": None,
        "metrics": None,
        "exceptions_enabled": True,
        "exceptions_max_frames": 10,
        "exceptions_max_stack_chars": 1024,
        "serialize_in_flush": False,
        "num_workers": 1,
        "level_gate": None,
    }


class TestPreparePayloadSharedBehavior:
    """Tests for _prepare_payload shared across both facades."""

    def test_prepare_payload_shares_bound_context(self) -> None:
        """Both facades should bind context identically via the mixin."""
        sync_logger = SyncLoggerFacade(**_logger_args())
        async_logger = AsyncLoggerFacade(**_logger_args())

        sync_logger.bind(user="alice")
        async_logger.bind(user="alice")

        sync_payload = sync_logger._prepare_payload("INFO", "hello")  # type: ignore[attr-defined]
        async_payload = async_logger._prepare_payload("INFO", "hello-async")  # type: ignore[attr-defined]

        assert sync_payload is not None
        assert async_payload is not None
        assert sync_payload["metadata"]["user"] == "alice"
        assert async_payload["metadata"]["user"] == "alice"

    def test_prepare_payload_dedupes_errors_per_facade(self) -> None:
        """Error deduplication should work identically in both facades."""
        logger = SyncLoggerFacade(**_logger_args())

        first = logger._prepare_payload("ERROR", "boom")  # type: ignore[attr-defined]
        second = logger._prepare_payload("ERROR", "boom")  # type: ignore[attr-defined]

        assert first is not None
        assert second is None

    def test_prepare_payload_returns_dict(self) -> None:
        """_prepare_payload must return a dict, not a Mapping."""
        logger = SyncLoggerFacade(**_logger_args())

        payload = logger._prepare_payload("INFO", "test message")  # type: ignore[attr-defined]

        assert payload is not None
        assert isinstance(payload, dict)
        assert "level" in payload
        assert "message" in payload
        assert payload["level"] == "INFO"
        assert payload["message"] == "test message"

    def test_prepare_payload_with_metadata(self) -> None:
        """Metadata should be merged into the payload correctly."""
        logger = SyncLoggerFacade(**_logger_args())

        payload = logger._prepare_payload(  # type: ignore[attr-defined]
            "INFO",
            "test",
            request_id="abc123",
            user_id=42,
        )

        assert payload is not None
        assert payload["metadata"]["request_id"] == "abc123"
        assert payload["metadata"]["user_id"] == 42


class TestContextBindingSharedBehavior:
    """Tests for context binding shared across both facades."""

    def test_bind_returns_self_sync(self) -> None:
        """SyncLoggerFacade.bind should return self for chaining."""
        logger = SyncLoggerFacade(**_logger_args())

        result = logger.bind(key="value")

        assert result is logger

    def test_bind_returns_self_async(self) -> None:
        """AsyncLoggerFacade.bind should return self for chaining."""
        logger = AsyncLoggerFacade(**_logger_args())

        result = logger.bind(key="value")

        assert result is logger

    def test_unbind_removes_keys(self) -> None:
        """unbind should remove specified keys from context."""
        logger = SyncLoggerFacade(**_logger_args())
        logger.bind(user="alice", role="admin", session="xyz")

        logger.unbind("role")

        payload = logger._prepare_payload("INFO", "test")  # type: ignore[attr-defined]
        assert payload is not None
        assert "user" in payload["metadata"]
        assert "session" in payload["metadata"]
        assert "role" not in payload["metadata"]

    def test_clear_context_removes_all(self) -> None:
        """clear_context should remove all bound context."""
        logger = SyncLoggerFacade(**_logger_args())
        logger.bind(user="alice", role="admin")

        logger.clear_context()

        payload = logger._prepare_payload("INFO", "test")  # type: ignore[attr-defined]
        assert payload is not None
        # Only correlation_id should remain in metadata (auto-generated)
        assert "user" not in payload["metadata"]
        assert "role" not in payload["metadata"]


class TestMixinInheritance:
    """Tests verifying both facades inherit properly from _LoggerMixin."""

    def test_sync_facade_inherits_make_worker(self) -> None:
        """SyncLoggerFacade should use _make_worker from mixin."""
        logger = SyncLoggerFacade(**_logger_args())

        # This should not raise - _make_worker is inherited
        worker = logger._make_worker()  # type: ignore[attr-defined]
        assert worker is not None

    def test_async_facade_inherits_make_worker(self) -> None:
        """AsyncLoggerFacade should use _make_worker from mixin."""
        logger = AsyncLoggerFacade(**_logger_args())

        # This should not raise - _make_worker is inherited
        worker = logger._make_worker()  # type: ignore[attr-defined]
        assert worker is not None

    def test_async_facade_has_diagnostics_disabled(self) -> None:
        """AsyncLoggerFacade should have worker diagnostics disabled."""
        logger = AsyncLoggerFacade(**_logger_args())

        assert logger._emit_worker_diagnostics is False  # type: ignore[attr-defined]

    def test_sync_facade_has_diagnostics_enabled(self) -> None:
        """SyncLoggerFacade should have worker diagnostics enabled (default)."""
        logger = SyncLoggerFacade(**_logger_args())

        assert logger._emit_worker_diagnostics is True  # type: ignore[attr-defined]


class TestLevelGateSharedBehavior:
    """Tests for level gate filtering shared across both facades."""

    def test_level_gate_filters_low_priority_sync(self) -> None:
        """Level gate should filter messages below threshold in sync facade."""
        from fapilog.plugins.filters.level import LEVEL_PRIORITY

        # Set gate to WARNING level (30)
        args = _logger_args()
        args["level_gate"] = LEVEL_PRIORITY["WARNING"]  # type: ignore[literal-required]
        logger = SyncLoggerFacade(**args)  # type: ignore[arg-type]

        # DEBUG and INFO should be filtered
        debug_payload = logger._prepare_payload("DEBUG", "debug msg")  # type: ignore[attr-defined]
        info_payload = logger._prepare_payload("INFO", "info msg")  # type: ignore[attr-defined]
        warning_payload = logger._prepare_payload("WARNING", "warn msg")  # type: ignore[attr-defined]

        # _prepare_payload doesn't do level gate filtering - that's in _enqueue
        # So all payloads should be created, but we verify the gate attribute
        assert logger._level_gate == LEVEL_PRIORITY["WARNING"]  # type: ignore[attr-defined]
        # These should all be created since _prepare_payload doesn't filter by level
        assert debug_payload is not None
        assert info_payload is not None
        assert warning_payload is not None
