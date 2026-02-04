"""Integration tests for custom log level registration (Story 10.47).

These tests verify the full pipeline from level registration through
logger creation, event processing, filtering, and sink output.
"""

from __future__ import annotations

import pytest


class TestCustomLevelsFullPipeline:
    """Test custom levels through the complete logging pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_with_custom_levels(self) -> None:
        """Custom levels work end-to-end: register -> log -> filter -> sink."""
        from fapilog.core.levels import _reset_registry

        _reset_registry()

        import fapilog
        from fapilog import Settings

        # Register custom levels before logger creation
        # Note: AUDIT and SECURITY are now built-in levels (Story 1.38)
        fapilog.register_level("TRACE", priority=5, add_method=True)
        fapilog.register_level("NOTICE", priority=25, add_method=True)

        # Capture events at the sink
        captured_events: list[dict] = []

        class CaptureSink:
            name = "capture"

            async def write(self, event: dict) -> bool:
                captured_events.append(event)
                return True

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

        # Use DEBUG level to allow TRACE through
        settings = Settings(core={"log_level": "DEBUG"})
        logger = fapilog.get_logger(
            sinks=[CaptureSink()], settings=settings, reuse=False
        )

        # Log using dynamic methods (type: ignore for dynamically added methods)
        logger.trace("trace event", component="auth")  # type: ignore[attr-defined]
        logger.notice("notice event", user_id="u123", action="login")  # type: ignore[attr-defined]
        logger.info("info event")
        logger.error("error event")

        await logger.stop_and_drain()

        # Verify all events reached the sink with correct levels
        assert len(captured_events) == 4

        levels = [e["level"] for e in captured_events]
        assert "TRACE" in levels
        assert "NOTICE" in levels
        assert "INFO" in levels
        assert "ERROR" in levels

        # Verify metadata passed through
        trace_event = next(e for e in captured_events if e["level"] == "TRACE")
        assert trace_event["message"] == "trace event"
        assert trace_event["data"]["component"] == "auth"

        notice_event = next(e for e in captured_events if e["level"] == "NOTICE")
        assert notice_event["message"] == "notice event"
        # user_id goes to context (ID fields), action goes to data
        assert notice_event["context"]["user_id"] == "u123"
        assert notice_event["data"]["action"] == "login"

    @pytest.mark.asyncio
    async def test_custom_level_filtering_in_pipeline(self) -> None:
        """Custom levels are correctly filtered based on min_level."""
        from fapilog.core.levels import _reset_registry

        _reset_registry()

        import fapilog
        from fapilog import Settings

        fapilog.register_level("TRACE", priority=5, add_method=True)
        fapilog.register_level("NOTICE", priority=25, add_method=True)

        captured_events: list[dict] = []

        class CaptureSink:
            name = "capture"

            async def write(self, event: dict) -> bool:
                captured_events.append(event)
                return True

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

        # INFO level (20) should filter out TRACE (5) but allow NOTICE (25)
        settings = Settings(core={"log_level": "INFO"})
        logger = fapilog.get_logger(
            sinks=[CaptureSink()], settings=settings, reuse=False
        )

        logger.trace("should be dropped")  # type: ignore[attr-defined]  # priority 5 < 20
        logger.info("should appear")  # priority 20 >= 20
        logger.notice("should appear")  # type: ignore[attr-defined]  # priority 25 >= 20

        await logger.stop_and_drain()

        # Only INFO and NOTICE should reach the sink
        assert len(captured_events) == 2
        levels = {e["level"] for e in captured_events}
        assert levels == {"INFO", "NOTICE"}

    @pytest.mark.asyncio
    async def test_async_logger_with_custom_levels(self) -> None:
        """Custom levels work with async logger facade."""
        from fapilog.core.levels import _reset_registry

        _reset_registry()

        import fapilog
        from fapilog import Settings

        fapilog.register_level("NOTICE", priority=22, add_method=True)

        captured_events: list[dict] = []

        class CaptureSink:
            name = "capture"

            async def write(self, event: dict) -> bool:
                captured_events.append(event)
                return True

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

        settings = Settings(core={"log_level": "DEBUG"})
        logger = await fapilog.get_async_logger(
            sinks=[CaptureSink()], settings=settings, reuse=False
        )

        await logger.notice("notice event", priority="medium")  # type: ignore[attr-defined]
        await logger.info("info event")

        await logger.drain()

        assert len(captured_events) == 2
        notice_event = next(e for e in captured_events if e["level"] == "NOTICE")
        assert notice_event["data"]["priority"] == "medium"

    @pytest.mark.asyncio
    async def test_routing_with_custom_levels_integration(self) -> None:
        """Custom levels route to correct sinks in full pipeline."""
        from fapilog.core.levels import _reset_registry

        _reset_registry()

        import fapilog
        from fapilog import Settings

        fapilog.register_level("NOTICE", priority=25, add_method=True)

        notice_events: list[dict] = []
        general_events: list[dict] = []

        class NoticeSink:
            name = "notice_sink"

            async def write(self, event: dict) -> bool:
                notice_events.append(event)
                return True

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

        class GeneralSink:
            name = "general_sink"

            async def write(self, event: dict) -> bool:
                general_events.append(event)
                return True

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

        settings = Settings(
            core={"log_level": "DEBUG", "sinks": ["notice_sink", "general_sink"]},
            sink_routing={
                "enabled": True,
                "rules": [
                    {"levels": ["NOTICE"], "sinks": ["notice_sink"]},
                    {"levels": ["INFO", "WARNING", "ERROR"], "sinks": ["general_sink"]},
                ],
            },
        )

        logger = fapilog.get_logger(
            sinks=[NoticeSink(), GeneralSink()], settings=settings, reuse=False
        )

        logger.notice("notice event", action="access")  # type: ignore[attr-defined]
        logger.info("general event")

        await logger.stop_and_drain()

        # NOTICE should go to notice_sink, INFO to general_sink
        assert len(notice_events) == 1
        assert notice_events[0]["level"] == "NOTICE"

        assert len(general_events) == 1
        assert general_events[0]["level"] == "INFO"

    def test_registry_freeze_prevents_late_registration(self) -> None:
        """Registry freeze prevents registration after logger creation."""
        from fapilog.core.levels import _reset_registry

        _reset_registry()

        import fapilog

        # Create a logger first
        _ = fapilog.get_logger(reuse=False)

        # Attempting to register after logger creation should fail
        with pytest.raises(RuntimeError, match="after loggers have been created"):
            fapilog.register_level("LATE", priority=15)

    @pytest.mark.asyncio
    async def test_multiple_custom_levels_ordering(self) -> None:
        """Multiple custom levels maintain correct priority ordering via level filter."""
        from fapilog.core.levels import _reset_registry

        _reset_registry()

        import fapilog
        from fapilog import Settings

        # Register levels in non-priority order
        fapilog.register_level("ALERT", priority=45, add_method=True)
        fapilog.register_level("TRACE", priority=5, add_method=True)
        fapilog.register_level("NOTICE", priority=22, add_method=True)

        captured_events: list[dict] = []

        class CaptureSink:
            name = "capture"

            async def write(self, event: dict) -> bool:
                captured_events.append(event)
                return True

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

        # Use level filter with custom min_level (NOTICE has priority 22)
        # This filters TRACE (5) but allows NOTICE (22), WARNING (30), ALERT (45)
        settings = Settings(
            core={"log_level": "DEBUG", "filters": ["level"]},
            filter_config={"level": {"min_level": "NOTICE"}},
        )
        logger = fapilog.get_logger(
            sinks=[CaptureSink()], settings=settings, reuse=False
        )

        logger.trace("should be dropped")  # type: ignore[attr-defined]  # 5 < 22
        logger.notice("should appear")  # type: ignore[attr-defined]  # 22 >= 22
        logger.alert("should appear")  # type: ignore[attr-defined]  # 45 >= 22

        await logger.stop_and_drain()

        assert len(captured_events) == 2
        levels = {e["level"] for e in captured_events}
        assert levels == {"NOTICE", "ALERT"}
