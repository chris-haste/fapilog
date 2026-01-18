"""Tests for audit trail instance management (Story 4.43)."""

from pathlib import Path

import pytest

from fapilog_audit.audit import (
    get_audit_trail,
    reset_all_audit_trails,
    reset_audit_trail,
)


class TestResetAuditTrail:
    """AC1: Reset Function for Tests."""

    @pytest.mark.asyncio
    async def test_reset_clears_default_instance(self) -> None:
        """After reset, get_audit_trail returns a new instance."""
        trail1 = await get_audit_trail()
        await reset_audit_trail()
        trail2 = await get_audit_trail()

        assert trail1 is not trail2

    @pytest.mark.asyncio
    async def test_reset_stops_running_trail(self) -> None:
        """Reset stops the audit trail before clearing it."""
        trail = await get_audit_trail()
        # Verify task is actively running (not done)
        assert trail._processing_task is not None and not trail._processing_task.done()

        await reset_audit_trail()

        # After stop, processing task is cleared
        assert trail._processing_task is None


class TestNamedInstances:
    """AC2: Named Instances Supported."""

    @pytest.mark.asyncio
    async def test_named_instances_are_isolated(self) -> None:
        """Named instances are separate from each other."""
        admin_trail = await get_audit_trail(name="admin-operations")
        user_trail = await get_audit_trail(name="user-activity")

        assert admin_trail is not user_trail

    @pytest.mark.asyncio
    async def test_named_instance_separate_from_default(self) -> None:
        """Named instance is separate from default global instance."""
        default_trail = await get_audit_trail()
        admin_trail = await get_audit_trail(name="admin-operations")

        assert default_trail is not admin_trail

    @pytest.mark.asyncio
    async def test_same_name_returns_same_instance(self) -> None:
        """Requesting the same name returns the cached instance."""
        trail1 = await get_audit_trail(name="test-trail")
        trail2 = await get_audit_trail(name="test-trail")

        assert trail1 is trail2

    @pytest.mark.asyncio
    async def test_reset_named_instance(self) -> None:
        """Reset can target a specific named instance."""
        trail1 = await get_audit_trail(name="test-trail")
        await reset_audit_trail(name="test-trail")
        trail2 = await get_audit_trail(name="test-trail")

        assert trail1 is not trail2

    @pytest.mark.asyncio
    async def test_reset_named_does_not_affect_default(self) -> None:
        """Resetting a named instance doesn't affect the default."""
        default_trail = await get_audit_trail()
        await get_audit_trail(name="test-trail")
        await reset_audit_trail(name="test-trail")

        # Default should still be the same instance
        current_default = await get_audit_trail()
        assert default_trail is current_default


class TestConfigurationAfterReset:
    """AC3: Configuration Respected on Reset."""

    @pytest.mark.asyncio
    async def test_new_config_applied_after_reset(self, tmp_path: Path) -> None:
        """After reset, new configuration is applied."""
        path1 = tmp_path / "trail1"
        path2 = tmp_path / "trail2"

        trail1 = await get_audit_trail(storage_path=path1)
        assert trail1.storage_path == path1

        await reset_audit_trail()

        trail2 = await get_audit_trail(storage_path=path2)
        assert trail2.storage_path == path2


class TestBackwardCompatibility:
    """AC4: Backward Compatible."""

    @pytest.mark.asyncio
    async def test_get_audit_trail_without_args_works(self) -> None:
        """Existing code using get_audit_trail() continues to work."""
        from fapilog_audit.audit import AuditTrail

        trail = await get_audit_trail()

        # Verify we got a valid, running AuditTrail instance
        assert isinstance(trail, AuditTrail)
        assert trail._processing_task is not None and not trail._processing_task.done()

    @pytest.mark.asyncio
    async def test_subsequent_calls_return_same_instance(self) -> None:
        """Multiple calls to get_audit_trail() return the same instance."""
        trail1 = await get_audit_trail()
        trail2 = await get_audit_trail()

        assert trail1 is trail2


class TestResetAllAuditTrails:
    """Test reset_all_audit_trails function."""

    @pytest.mark.asyncio
    async def test_reset_all_clears_default_and_named(self) -> None:
        """reset_all_audit_trails clears all instances."""
        default_trail = await get_audit_trail()
        named_trail = await get_audit_trail(name="test-trail")

        await reset_all_audit_trails()

        new_default = await get_audit_trail()
        new_named = await get_audit_trail(name="test-trail")

        assert default_trail is not new_default
        assert named_trail is not new_named
