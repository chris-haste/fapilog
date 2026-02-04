"""Tests for AUDIT and SECURITY log levels (Story 1.38)."""

from __future__ import annotations

from typing import Any

import pytest

from fapilog.core.levels import _reset_registry, get_all_levels, get_level_priority


class TestAuditLevel:
    """AC1: AUDIT level exists with correct priority."""

    def test_audit_level_value(self) -> None:
        """AUDIT level has numeric value 60."""
        _reset_registry()
        assert get_level_priority("AUDIT") == 60

    def test_audit_level_above_critical(self) -> None:
        """AUDIT level is higher than CRITICAL."""
        _reset_registry()
        assert get_level_priority("AUDIT") > get_level_priority("CRITICAL")

    def test_audit_in_all_levels(self) -> None:
        """AUDIT appears in get_all_levels()."""
        _reset_registry()
        levels = get_all_levels()
        assert "AUDIT" in levels
        assert levels["AUDIT"] == 60

    def test_audit_case_insensitive(self) -> None:
        """AUDIT level lookup is case-insensitive."""
        _reset_registry()
        assert get_level_priority("audit") == 60
        assert get_level_priority("Audit") == 60
        assert get_level_priority("AUDIT") == 60


class TestSecurityLevel:
    """AC2: SECURITY level exists with correct priority."""

    def test_security_level_value(self) -> None:
        """SECURITY level has numeric value 70."""
        _reset_registry()
        assert get_level_priority("SECURITY") == 70

    def test_security_level_above_audit(self) -> None:
        """SECURITY level is higher than AUDIT."""
        _reset_registry()
        assert get_level_priority("SECURITY") > get_level_priority("AUDIT")

    def test_security_in_all_levels(self) -> None:
        """SECURITY appears in get_all_levels()."""
        _reset_registry()
        levels = get_all_levels()
        assert "SECURITY" in levels
        assert levels["SECURITY"] == 70

    def test_security_case_insensitive(self) -> None:
        """SECURITY level lookup is case-insensitive."""
        _reset_registry()
        assert get_level_priority("security") == 70
        assert get_level_priority("Security") == 70
        assert get_level_priority("SECURITY") == 70


class TestLevelOrdering:
    """AC4: Standard level ordering is preserved."""

    def test_complete_level_ordering(self) -> None:
        """Levels are ordered: DEBUG < INFO < WARNING < ERROR < CRITICAL < AUDIT < SECURITY."""
        _reset_registry()
        assert get_level_priority("DEBUG") < get_level_priority("INFO")
        assert get_level_priority("INFO") < get_level_priority("WARNING")
        assert get_level_priority("WARNING") < get_level_priority("ERROR")
        assert get_level_priority("ERROR") < get_level_priority("CRITICAL")
        assert get_level_priority("CRITICAL") < get_level_priority("AUDIT")
        assert get_level_priority("AUDIT") < get_level_priority("SECURITY")

    def test_fatal_alias_preserved(self) -> None:
        """FATAL remains an alias for CRITICAL (50)."""
        _reset_registry()
        assert get_level_priority("FATAL") == get_level_priority("CRITICAL")
        assert get_level_priority("FATAL") == 50

    def test_warn_alias_preserved(self) -> None:
        """WARN remains an alias for WARNING (30)."""
        _reset_registry()
        assert get_level_priority("WARN") == get_level_priority("WARNING")
        assert get_level_priority("WARN") == 30


class TestLoggerMethods:
    """AC3: Logger has audit() and security() methods."""

    @pytest.mark.asyncio
    async def test_sync_logger_has_audit_method(self) -> None:
        """SyncLoggerFacade has audit() method."""
        _reset_registry()

        events: list[dict[str, Any]] = []

        class CaptureSink:
            name = "capture"

            async def write(self, event: dict[str, Any]) -> bool:
                events.append(event)
                return True

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

        import fapilog

        logger = fapilog.get_logger(sinks=[CaptureSink()], reuse=False)

        assert hasattr(logger, "audit")
        logger.audit("User login", user_id="123", ip="10.0.0.1")

        await logger.stop_and_drain()

        assert len(events) == 1
        assert events[0]["level"] == "AUDIT"
        assert events[0]["message"] == "User login"

    @pytest.mark.asyncio
    async def test_sync_logger_has_security_method(self) -> None:
        """SyncLoggerFacade has security() method."""
        _reset_registry()

        events: list[dict[str, Any]] = []

        class CaptureSink:
            name = "capture"

            async def write(self, event: dict[str, Any]) -> bool:
                events.append(event)
                return True

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

        import fapilog

        logger = fapilog.get_logger(sinks=[CaptureSink()], reuse=False)

        assert hasattr(logger, "security")
        logger.security("Failed auth attempt", user_id="123", attempts=5)

        await logger.stop_and_drain()

        assert len(events) == 1
        assert events[0]["level"] == "SECURITY"
        assert events[0]["message"] == "Failed auth attempt"

    @pytest.mark.asyncio
    async def test_async_logger_has_audit_method(self) -> None:
        """AsyncLoggerFacade has audit() method."""
        _reset_registry()

        events: list[dict[str, Any]] = []

        class CaptureSink:
            name = "capture"

            async def write(self, event: dict[str, Any]) -> bool:
                events.append(event)
                return True

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

        import fapilog

        logger = await fapilog.get_async_logger(sinks=[CaptureSink()], reuse=False)

        assert hasattr(logger, "audit")
        await logger.audit("User login", user_id="456")

        await logger.drain()

        assert len(events) == 1
        assert events[0]["level"] == "AUDIT"

    @pytest.mark.asyncio
    async def test_async_logger_has_security_method(self) -> None:
        """AsyncLoggerFacade has security() method."""
        _reset_registry()

        events: list[dict[str, Any]] = []

        class CaptureSink:
            name = "capture"

            async def write(self, event: dict[str, Any]) -> bool:
                events.append(event)
                return True

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

        import fapilog

        logger = await fapilog.get_async_logger(sinks=[CaptureSink()], reuse=False)

        assert hasattr(logger, "security")
        await logger.security("Suspicious activity", source="firewall")

        await logger.drain()

        assert len(events) == 1
        assert events[0]["level"] == "SECURITY"


class TestProtectedLevels:
    """AC7: AUDIT and SECURITY included in default protected_levels."""

    def test_default_protected_levels_includes_audit(self) -> None:
        """Default protected_levels includes AUDIT."""
        from fapilog import Settings

        settings = Settings()
        assert "AUDIT" in settings.core.protected_levels

    def test_default_protected_levels_includes_security(self) -> None:
        """Default protected_levels includes SECURITY."""
        from fapilog import Settings

        settings = Settings()
        assert "SECURITY" in settings.core.protected_levels

    def test_default_protected_levels_complete(self) -> None:
        """Default protected_levels includes all expected levels."""
        from fapilog import Settings

        settings = Settings()
        expected = {"ERROR", "CRITICAL", "FATAL", "AUDIT", "SECURITY"}
        actual = set(settings.core.protected_levels)
        assert expected == actual


class TestLevelFiltering:
    """AC5: Level filtering works with AUDIT and SECURITY levels."""

    @pytest.mark.asyncio
    async def test_level_filter_at_audit_filters_error(self) -> None:
        """Setting min level to AUDIT filters out ERROR."""
        _reset_registry()

        from fapilog.plugins.filters.level import LevelFilter

        filter_instance = LevelFilter(config={"min_level": "AUDIT"})

        error_event = {"level": "ERROR", "message": "error msg"}
        audit_event = {"level": "AUDIT", "message": "audit msg"}
        security_event = {"level": "SECURITY", "message": "security msg"}

        result_error = await filter_instance.filter(error_event)
        result_audit = await filter_instance.filter(audit_event)
        result_security = await filter_instance.filter(security_event)

        assert result_error is None  # ERROR (40) < AUDIT (60), filtered
        assert result_audit == audit_event  # AUDIT (60) >= AUDIT (60), passes
        assert result_security == security_event  # SECURITY (70) >= AUDIT (60), passes

    @pytest.mark.asyncio
    async def test_level_filter_at_security_filters_audit(self) -> None:
        """Setting min level to SECURITY filters out AUDIT."""
        _reset_registry()

        from fapilog.plugins.filters.level import LevelFilter

        filter_instance = LevelFilter(config={"min_level": "SECURITY"})

        audit_event = {"level": "AUDIT", "message": "audit msg"}
        security_event = {"level": "SECURITY", "message": "security msg"}

        result_audit = await filter_instance.filter(audit_event)
        result_security = await filter_instance.filter(security_event)

        assert result_audit is None  # AUDIT (60) < SECURITY (70), filtered
        assert (
            result_security == security_event
        )  # SECURITY (70) >= SECURITY (70), passes


class TestLevelRouting:
    """AC6: Level routing works with AUDIT and SECURITY levels."""

    @pytest.mark.asyncio
    async def test_routing_audit_to_dedicated_sink(self) -> None:
        """AUDIT events can be routed to a dedicated sink."""
        _reset_registry()

        from fapilog.core.routing import RoutingSinkWriter

        audit_events: list[dict[str, Any]] = []
        other_events: list[dict[str, Any]] = []

        class AuditSink:
            name = "audit_sink"

            async def write(self, event: dict[str, Any]) -> bool:
                audit_events.append(event)
                return True

        class OtherSink:
            name = "other_sink"

            async def write(self, event: dict[str, Any]) -> bool:
                other_events.append(event)
                return True

        sinks = [AuditSink(), OtherSink()]
        rules = [
            ({"AUDIT"}, ["audit_sink"]),
            ({"INFO", "ERROR"}, ["other_sink"]),
        ]

        writer = RoutingSinkWriter(sinks, rules, fallback_sink_names=[])

        await writer.write({"level": "AUDIT", "message": "audit event"})
        await writer.write({"level": "INFO", "message": "info event"})

        assert len(audit_events) == 1
        assert audit_events[0]["level"] == "AUDIT"
        assert len(other_events) == 1
        assert other_events[0]["level"] == "INFO"

    @pytest.mark.asyncio
    async def test_routing_security_to_siem_sink(self) -> None:
        """SECURITY events can be routed to a SIEM sink."""
        _reset_registry()

        from fapilog.core.routing import RoutingSinkWriter

        siem_events: list[dict[str, Any]] = []

        class SiemSink:
            name = "siem_sink"

            async def write(self, event: dict[str, Any]) -> bool:
                siem_events.append(event)
                return True

        sinks = [SiemSink()]
        rules = [({"SECURITY"}, ["siem_sink"])]

        writer = RoutingSinkWriter(sinks, rules, fallback_sink_names=[])

        await writer.write({"level": "SECURITY", "message": "suspicious activity"})

        assert len(siem_events) == 1
        assert siem_events[0]["level"] == "SECURITY"
