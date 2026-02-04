"""Tests for custom log level registration (Story 10.47)."""

from __future__ import annotations

import pytest


class TestPublicAPI:
    """Test public API exports."""

    def test_register_level_exported_from_fapilog(self) -> None:
        """register_level is available from fapilog package."""
        import fapilog

        assert hasattr(fapilog, "register_level")
        assert callable(fapilog.register_level)


class TestRegisterLevel:
    """Test register_level() function."""

    def test_register_custom_level(self) -> None:
        """AC1: Custom levels can be registered."""
        from fapilog.core.levels import (
            _reset_registry,
            get_all_levels,
            get_level_priority,
            register_level,
        )

        _reset_registry()  # Ensure clean state

        register_level("TRACE", priority=5)

        assert get_level_priority("TRACE") == 5
        assert "TRACE" in get_all_levels()

    def test_register_level_case_insensitive(self) -> None:
        """Level names are normalized to uppercase."""
        from fapilog.core.levels import (
            _reset_registry,
            get_level_priority,
            register_level,
        )

        _reset_registry()

        register_level("trace", priority=5)

        assert get_level_priority("trace") == 5
        assert get_level_priority("TRACE") == 5
        assert get_level_priority("Trace") == 5

    def test_register_level_duplicate_raises(self) -> None:
        """AC4: Duplicate name raises ValueError."""
        from fapilog.core.levels import _reset_registry, register_level

        _reset_registry()

        # Can't register existing standard level
        with pytest.raises(ValueError, match="already exists"):
            register_level("DEBUG", priority=5)

    def test_register_level_duplicate_custom_raises(self) -> None:
        """AC4: Duplicate custom level raises ValueError."""
        from fapilog.core.levels import _reset_registry, register_level

        _reset_registry()

        register_level("TRACE", priority=5)
        with pytest.raises(ValueError, match="already exists"):
            register_level("TRACE", priority=3)

    def test_register_level_invalid_priority_negative(self) -> None:
        """AC4: Negative priority raises ValueError."""
        from fapilog.core.levels import _reset_registry, register_level

        _reset_registry()

        with pytest.raises(ValueError, match="must be 0-99"):
            register_level("CUSTOM", priority=-1)

    def test_register_level_invalid_priority_too_high(self) -> None:
        """AC4: Priority > 99 raises ValueError."""
        from fapilog.core.levels import _reset_registry, register_level

        _reset_registry()

        with pytest.raises(ValueError, match="must be 0-99"):
            register_level("CUSTOM", priority=100)

    def test_register_level_boundary_priorities(self) -> None:
        """Boundary values 0 and 99 are valid."""
        from fapilog.core.levels import (
            _reset_registry,
            get_level_priority,
            register_level,
        )

        _reset_registry()

        register_level("LOWEST", priority=0)
        register_level("HIGHEST", priority=99)

        assert get_level_priority("LOWEST") == 0
        assert get_level_priority("HIGHEST") == 99

    def test_get_level_priority_unknown_returns_info(self) -> None:
        """Unknown levels default to INFO priority (20)."""
        from fapilog.core.levels import _reset_registry, get_level_priority

        _reset_registry()

        assert get_level_priority("UNKNOWN_LEVEL") == 20

    def test_get_all_levels_includes_defaults(self) -> None:
        """get_all_levels() includes default and custom levels."""
        from fapilog.core.levels import _reset_registry, get_all_levels, register_level

        _reset_registry()

        register_level("NOTICE", priority=25)

        levels = get_all_levels()
        # Default levels
        assert levels["DEBUG"] == 10
        assert levels["INFO"] == 20
        assert levels["WARNING"] == 30
        assert levels["ERROR"] == 40
        assert levels["CRITICAL"] == 50
        # Standard levels added in Story 1.38
        assert levels["AUDIT"] == 60
        assert levels["SECURITY"] == 70
        # Custom level
        assert levels["NOTICE"] == 25


class TestRegistryFreezing:
    """Test that registry freezes after logger creation."""

    def test_register_after_freeze_raises(self) -> None:
        """AC6: Registering after freeze raises RuntimeError."""
        from fapilog.core.levels import (
            _reset_registry,
            freeze_registry,
            register_level,
        )

        _reset_registry()
        freeze_registry()

        with pytest.raises(RuntimeError, match="after loggers have been created"):
            register_level("TRACE", priority=5)

    def test_freeze_idempotent(self) -> None:
        """Freezing multiple times is safe."""
        from fapilog.core.levels import _reset_registry, freeze_registry

        _reset_registry()
        freeze_registry()
        freeze_registry()  # Should not raise


class TestPendingMethods:
    """Test add_method flag for dynamic method generation."""

    def test_add_method_flag_stores_pending(self) -> None:
        """add_method=True stores level for later method generation."""
        from fapilog.core.levels import (
            _reset_registry,
            get_pending_methods,
            register_level,
        )

        _reset_registry()

        register_level("TRACE", priority=5, add_method=True)
        register_level("VERBOSE", priority=15, add_method=False)
        register_level("NOTICE", priority=22)  # default False

        pending = get_pending_methods()
        assert "TRACE" in pending
        assert "VERBOSE" not in pending
        assert "NOTICE" not in pending


class TestLevelFilterIntegration:
    """AC2: Level filtering works with custom levels."""

    @pytest.mark.asyncio
    async def test_level_filter_respects_custom_levels(self) -> None:
        """Level filter uses registry for priority lookup."""
        from fapilog.core.levels import _reset_registry, register_level
        from fapilog.plugins.filters.level import LevelFilter

        _reset_registry()
        register_level("TRACE", priority=5)

        # Level filter at INFO should drop TRACE
        filter_instance = LevelFilter(config={"min_level": "INFO"})

        trace_event = {"level": "TRACE", "message": "trace msg"}
        info_event = {"level": "INFO", "message": "info msg"}

        result_trace = await filter_instance.filter(trace_event)
        result_info = await filter_instance.filter(info_event)

        assert result_trace is None  # TRACE (5) < INFO (20), should be dropped
        assert result_info == info_event  # INFO (20) >= INFO (20), should pass

    @pytest.mark.asyncio
    async def test_level_filter_custom_min_level(self) -> None:
        """Level filter can use custom level as min_level."""
        from fapilog.core.levels import _reset_registry, register_level
        from fapilog.plugins.filters.level import LevelFilter

        _reset_registry()
        register_level("NOTICE", priority=25)

        # Level filter at NOTICE should drop INFO but pass WARNING
        filter_instance = LevelFilter(config={"min_level": "NOTICE"})

        info_event = {"level": "INFO", "message": "info msg"}
        notice_event = {"level": "NOTICE", "message": "notice msg"}
        warning_event = {"level": "WARNING", "message": "warning msg"}

        result_info = await filter_instance.filter(info_event)
        result_notice = await filter_instance.filter(notice_event)
        result_warning = await filter_instance.filter(warning_event)

        assert result_info is None  # INFO (20) < NOTICE (25)
        assert result_notice == notice_event  # NOTICE (25) >= NOTICE (25)
        assert result_warning == warning_event  # WARNING (30) >= NOTICE (25)


class TestRoutingIntegration:
    """AC3: Routing rules can use custom levels."""

    @pytest.mark.asyncio
    async def test_routing_with_custom_level(self) -> None:
        """Routing writer routes events by custom level."""
        from fapilog.core.levels import _reset_registry, register_level
        from fapilog.core.routing import RoutingSinkWriter

        _reset_registry()
        register_level("NOTICE", priority=25)

        # Create mock sinks
        notice_events: list[dict] = []
        other_events: list[dict] = []

        class NoticeSink:
            name = "notice_sink"

            async def write(self, event: dict) -> bool:
                notice_events.append(event)
                return True

        class OtherSink:
            name = "other_sink"

            async def write(self, event: dict) -> bool:
                other_events.append(event)
                return True

        sinks = [NoticeSink(), OtherSink()]
        rules = [
            ({"NOTICE"}, ["notice_sink"]),
            ({"INFO", "WARNING", "ERROR"}, ["other_sink"]),
        ]

        writer = RoutingSinkWriter(sinks, rules, fallback_sink_names=[])

        # Route NOTICE to notice_sink
        await writer.write({"level": "NOTICE", "message": "notice event"})
        # Route INFO to other_sink
        await writer.write({"level": "INFO", "message": "info event"})

        assert len(notice_events) == 1
        assert notice_events[0]["level"] == "NOTICE"
        assert len(other_events) == 1
        assert other_events[0]["level"] == "INFO"

    @pytest.mark.asyncio
    async def test_routing_custom_level_case_insensitive(self) -> None:
        """Routing matches custom levels case-insensitively."""
        from fapilog.core.levels import _reset_registry, register_level
        from fapilog.core.routing import RoutingSinkWriter

        _reset_registry()
        register_level("TRACE", priority=5)

        events: list[dict] = []

        class TestSink:
            name = "test_sink"

            async def write(self, event: dict) -> bool:
                events.append(event)
                return True

        sinks = [TestSink()]
        rules = [({"trace"}, ["test_sink"])]  # lowercase in rule

        writer = RoutingSinkWriter(sinks, rules, fallback_sink_names=[])

        # Event with uppercase level should still match
        await writer.write({"level": "TRACE", "message": "trace event"})

        assert len(events) == 1


class TestDynamicMethodGeneration:
    """AC5: Dynamic logger methods for custom levels."""

    @pytest.mark.asyncio
    async def test_sync_logger_has_dynamic_method(self) -> None:
        """Sync logger gets dynamic method for custom level with add_method=True."""
        from fapilog.core.levels import _reset_registry, register_level

        _reset_registry()
        register_level("TRACE", priority=5, add_method=True)

        # Create a mock sink to capture events
        events: list[dict] = []

        class CaptureSink:
            name = "capture"

            async def write(self, event: dict) -> bool:
                events.append(event)
                return True

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

        import fapilog
        from fapilog import Settings

        # Use DEBUG log level to allow TRACE (priority=5) through
        settings = Settings(core={"log_level": "DEBUG"})
        logger = fapilog.get_logger(
            sinks=[CaptureSink()], settings=settings, reuse=False
        )

        # Should have trace() method
        assert hasattr(logger, "trace")
        logger.trace("test trace message", extra_field="value")

        # Drain to ensure event is processed
        await logger.stop_and_drain()

        assert len(events) == 1
        assert events[0]["level"] == "TRACE"
        assert events[0]["message"] == "test trace message"

    @pytest.mark.asyncio
    async def test_async_logger_has_dynamic_method(self) -> None:
        """Async logger gets dynamic method for custom level with add_method=True."""
        from fapilog.core.levels import _reset_registry, register_level

        _reset_registry()
        register_level("NOTICE", priority=25, add_method=True)

        # Create a mock sink to capture events
        events: list[dict] = []

        class CaptureSink:
            name = "capture"

            async def write(self, event: dict) -> bool:
                events.append(event)
                return True

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

        import fapilog
        from fapilog import Settings

        # NOTICE has priority 25 which is above INFO (20), so default settings work
        # But use DEBUG to be safe and consistent with other tests
        settings = Settings(core={"log_level": "DEBUG"})
        logger = await fapilog.get_async_logger(
            sinks=[CaptureSink()], settings=settings, reuse=False
        )

        # Should have notice() method
        assert hasattr(logger, "notice")
        await logger.notice("user action", user_id="123")

        # Drain to ensure event is processed
        await logger.drain()

        assert len(events) == 1
        assert events[0]["level"] == "NOTICE"
        assert events[0]["message"] == "user action"

    def test_no_method_without_add_method_flag(self) -> None:
        """Levels registered without add_method=True don't get methods."""
        from fapilog.core.levels import _reset_registry, register_level

        _reset_registry()
        register_level("NOTICE", priority=22, add_method=False)

        import fapilog

        logger = fapilog.get_logger(reuse=False)

        # Should NOT have notice() method
        assert not hasattr(logger, "notice")


class TestLoggerCreationFreezesRegistry:
    """AC6: Registry freezes when logger is created."""

    def test_get_logger_freezes_registry(self) -> None:
        """Creating a sync logger freezes the registry."""
        from fapilog.core.levels import (
            _reset_registry,
            is_registry_frozen,
            register_level,
        )

        _reset_registry()
        assert not is_registry_frozen()

        register_level("TRACE", priority=5)

        import fapilog

        _ = fapilog.get_logger(reuse=False)

        assert is_registry_frozen()

        # Can't register after logger creation
        with pytest.raises(RuntimeError, match="after loggers have been created"):
            register_level("VERBOSE", priority=15)

    @pytest.mark.asyncio
    async def test_get_async_logger_freezes_registry(self) -> None:
        """Creating an async logger freezes the registry."""
        from fapilog.core.levels import (
            _reset_registry,
            is_registry_frozen,
            register_level,
        )

        _reset_registry()
        assert not is_registry_frozen()

        register_level("VERBOSE", priority=15)

        import fapilog

        logger = await fapilog.get_async_logger(reuse=False)
        await logger.drain()

        assert is_registry_frozen()

        # Can't register after logger creation
        with pytest.raises(RuntimeError, match="after loggers have been created"):
            register_level("TRACE", priority=5)
