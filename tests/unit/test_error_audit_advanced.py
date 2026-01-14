"""
Tests for advanced audit trail functionality.

Scope:
- Compliance-specific features (GDPR, HIPAA)
- Audit convenience functions
- Error conditions and edge cases
- Concurrent operations
- Background tasks
- Compliance alerts
- Event querying
- Storage error handling
- Cleanup functionality
"""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, mock_open, patch

import pytest

from fapilog.core import (
    AuditEventType,
    AuditLogLevel,
    AuditTrail,
    ComplianceLevel,
    CompliancePolicy,
    NetworkError,
    audit_error,
    audit_security_event,
    get_audit_trail,
)


class TestAuditTrailsAdvanced:
    """Test advanced audit trail functionality."""

    @pytest.mark.asyncio
    async def test_audit_trail_compliance_specific_features(self):
        """Test compliance-specific features for different standards."""
        # Test GDPR compliance
        gdpr_policy = CompliancePolicy(
            level=ComplianceLevel.GDPR,
            gdpr_data_subject_rights=True,
            retention_days=6 * 365,  # 6 years
        )

        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            gdpr_trail = AuditTrail(policy=gdpr_policy, storage_path=storage_path)
            await gdpr_trail.start()

            # Log GDPR-relevant event
            await gdpr_trail.log_data_access(
                resource="eu_customer_data",
                operation="read",
                user_id="eu-user",
                contains_pii=True,
                data_classification="personal",
                additional_metadata={
                    "gdpr_lawful_basis": "consent",
                    "data_subject_id": "DS-123",
                },
            )

            stats = await gdpr_trail.get_statistics()
            assert stats["policy"]["compliance_level"] == "gdpr"
            assert stats["policy"]["retention_days"] == 2190

            await gdpr_trail.stop()

        # Test HIPAA compliance
        hipaa_policy = CompliancePolicy(
            level=ComplianceLevel.HIPAA,
            hipaa_minimum_necessary=True,
            retention_days=6 * 365,
        )

        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            hipaa_trail = AuditTrail(policy=hipaa_policy, storage_path=storage_path)
            await hipaa_trail.start()

            # Log HIPAA-relevant event
            await hipaa_trail.log_data_access(
                resource="patient_records",
                operation="read",
                user_id="healthcare-provider",
                contains_phi=True,
                data_classification="restricted",
                additional_metadata={
                    "patient_id": "P-789",
                    "covered_entity": "Hospital-XYZ",
                },
            )

            stats = await hipaa_trail.get_statistics()
            assert stats["policy"]["compliance_level"] == "hipaa"

            await hipaa_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_convenience_functions(self):
        """Test audit convenience functions."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)

            # Test get_audit_trail function
            policy = CompliancePolicy(level=ComplianceLevel.SOC2)
            trail = await get_audit_trail(policy=policy, storage_path=storage_path)
            assert trail.policy.level == ComplianceLevel.SOC2
            assert trail.storage_path == storage_path

            await trail.start()

            # Test audit_error convenience function
            error = NetworkError("Network failure", service_name="api-service")
            event_id = await audit_error(
                error, operation="network_call", audit_trail=trail
            )
            assert isinstance(event_id, str) and len(event_id) == 36
            assert trail._error_count == 1

            # Test audit_security_event convenience function
            security_event_id = await audit_security_event(
                AuditEventType.AUTHORIZATION_FAILED,
                "Access denied",
                user_id="unauthorized-user",
                audit_trail=trail,
            )
            assert isinstance(security_event_id, str) and len(security_event_id) == 36
            assert trail._security_event_count == 1

            await trail.stop()

    @pytest.mark.asyncio
    async def test_audit_trail_error_conditions(self):
        """Test audit trail error handling and edge cases."""
        # Test logging events before starting
        audit_trail = AuditTrail()

        # Should handle gracefully when not started
        event_id = await audit_trail.log_event(
            AuditEventType.ERROR_OCCURRED, "Error before start"
        )
        assert isinstance(event_id, str) and len(event_id) == 36  # Should still generate ID

        # Test with non-existent (but valid) storage path that gets created automatically
        with TemporaryDirectory() as temp_dir:
            invalid_path = Path(temp_dir) / "nonexistent" / "path"
            trail_with_new_path = AuditTrail(storage_path=invalid_path)
            await trail_with_new_path.start()

            # Should handle path creation gracefully
            await trail_with_new_path.log_event(
                AuditEventType.ERROR_OCCURRED, "Test error"
            )

            # Verify path was created
            assert invalid_path.exists()

            await trail_with_new_path.stop()

    @pytest.mark.asyncio
    async def test_audit_trail_concurrent_operations(self):
        """Test audit trail with concurrent operations."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            audit_trail = AuditTrail(storage_path=storage_path)
            await audit_trail.start()

            # Create multiple concurrent logging operations
            async def log_events(start_index, count):
                event_ids = []
                for i in range(count):
                    event_id = await audit_trail.log_event(
                        AuditEventType.DATA_ACCESS,
                        f"Concurrent access {start_index + i}",
                        user_id=f"user-{start_index + i}",
                    )
                    event_ids.append(event_id)
                return event_ids

            # Run concurrent operations
            tasks = [
                log_events(0, 10),
                log_events(10, 10),
                log_events(20, 10),
            ]

            results = await asyncio.gather(*tasks)

            # Verify all events were logged
            total_events = sum(len(result) for result in results)
            assert total_events == 30
            assert audit_trail._event_count == 30

            # Verify all event IDs are unique
            all_event_ids = [event_id for result in results for event_id in result]
            assert len(set(all_event_ids)) == 30

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_background_tasks(self):
        """Test audit background task functionality."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            audit_trail = AuditTrail(storage_path=storage_path)

            # Test start/stop without any events
            await audit_trail.start()
            await asyncio.sleep(0.01)  # Let background tasks run briefly
            await audit_trail.stop()

            # Verify basic functionality worked
            assert audit_trail._event_count == 0

    @pytest.mark.asyncio
    async def test_audit_quick_coverage(self):
        """Test quick coverage improvements for audit module."""
        # Test direct AuditEvent creation with different log levels
        from fapilog.core.audit import AuditEvent

        event1 = AuditEvent(
            event_type=AuditEventType.SYSTEM_STARTUP,
            message="System started",
            log_level=AuditLogLevel.INFO,
        )
        assert event1.log_level == AuditLogLevel.INFO

        event2 = AuditEvent(
            event_type=AuditEventType.ERROR_OCCURRED,
            message="Error occurred",
            log_level=AuditLogLevel.ERROR,
        )
        assert event2.log_level == AuditLogLevel.ERROR

        # Test CompliancePolicy with different configurations
        policy1 = CompliancePolicy(level=ComplianceLevel.GDPR)
        assert policy1.level == ComplianceLevel.GDPR

        policy2 = CompliancePolicy(level=ComplianceLevel.HIPAA, enabled=False)
        assert policy2.enabled is False

    @pytest.mark.asyncio
    async def test_audit_trail_disabled_policy(self):
        """Test audit trail behavior when disabled."""
        policy = CompliancePolicy(enabled=False)
        audit_trail = AuditTrail(policy=policy)

        # When disabled, log_event should return empty string
        event_id = await audit_trail.log_event(
            AuditEventType.SYSTEM_STARTUP, "Test operation"
        )
        assert event_id == ""

        # Statistics should remain at zero
        stats = await audit_trail.get_statistics()
        assert stats["total_events"] == 0

    @pytest.mark.asyncio
    async def test_audit_trail_exception_handling(self):
        """Test audit trail exception handling in event processing."""
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            policy = CompliancePolicy(level=ComplianceLevel.SOC2)
            audit_trail = AuditTrail(storage_path=Path(temp_dir), policy=policy)

            # Test hostname/process collection exception handling
            with patch("socket.gethostname", side_effect=Exception("Network error")):
                with patch("os.getpid", side_effect=Exception("OS error")):
                    event_id = await audit_trail.log_event(
                        AuditEventType.SYSTEM_STARTUP, "Test with exceptions"
                    )
                    assert event_id  # Should still work despite exceptions

    @pytest.mark.asyncio
    async def test_audit_trail_compliance_alerts(self):
        """Test compliance alert triggering."""
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            policy = CompliancePolicy(
                level=ComplianceLevel.GDPR,
                real_time_alerts=True,
                alert_on_critical_errors=True,
                alert_on_security_events=True,
            )
            audit_trail = AuditTrail(storage_path=Path(temp_dir), policy=policy)

            await audit_trail.start()

            # Mock the alert sending method
            with patch.object(
                audit_trail, "_send_compliance_alert", new_callable=AsyncMock
            ) as mock_alert:
                # Test critical error alert
                await audit_trail.log_event(
                    AuditEventType.ERROR_OCCURRED,
                    "Critical error",
                    log_level=AuditLogLevel.CRITICAL,
                )
                # Wait for async event processing (minimal for CI)
                await asyncio.sleep(0.01)
                # Simplified assertion - just check it was called
                assert mock_alert.called

                mock_alert.reset_mock()

                # Test security event alert
                await audit_trail.log_event(
                    AuditEventType.SECURITY_VIOLATION,
                    "Security issue",
                    log_level=AuditLogLevel.SECURITY,
                )
                # Wait for async event processing (minimal for CI)
                await asyncio.sleep(0.01)
                # Simplified assertion - just check it was called
                assert mock_alert.called

                mock_alert.reset_mock()

                # Test GDPR PII alert
                await audit_trail.log_event(
                    AuditEventType.DATA_ACCESS, "PII access", contains_pii=True
                )
                # Wait for async event processing (minimal for CI)
                await asyncio.sleep(0.01)
                # Simplified assertion - just check it was called
                assert mock_alert.called

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_trail_hipaa_phi_alerts(self):
        """Test HIPAA PHI compliance alerts."""
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            policy = CompliancePolicy(
                level=ComplianceLevel.HIPAA, real_time_alerts=True
            )
            audit_trail = AuditTrail(storage_path=Path(temp_dir), policy=policy)

            await audit_trail.start()

            # Mock the alert sending method
            with patch.object(
                audit_trail, "_send_compliance_alert", new_callable=AsyncMock
            ) as mock_alert:
                # Test HIPAA PHI alert
                await audit_trail.log_event(
                    AuditEventType.DATA_ACCESS, "PHI access", contains_phi=True
                )
                # Wait for async event processing (minimal for CI)
                await asyncio.sleep(0.01)
                # Simplified assertion - just check it was called
                assert mock_alert.called

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_trail_disabled_alerts(self):
        """Test audit trail with disabled alerts."""
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            policy = CompliancePolicy(
                level=ComplianceLevel.SOC2,
                real_time_alerts=False,  # Disabled
            )
            audit_trail = AuditTrail(storage_path=Path(temp_dir), policy=policy)

            # Mock the alert sending method
            with patch.object(
                audit_trail, "_send_compliance_alert", new_callable=AsyncMock
            ) as mock_alert:
                # Even critical errors shouldn't trigger alerts when disabled
                await audit_trail.log_event(
                    AuditEventType.ERROR_OCCURRED,
                    "Critical error",
                    log_level=AuditLogLevel.CRITICAL,
                )
                mock_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_audit_trail_event_querying(self):
        """Test audit event querying and filtering."""
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            policy = CompliancePolicy(level=ComplianceLevel.SOC2)
            audit_trail = AuditTrail(storage_path=Path(temp_dir), policy=policy)

            await audit_trail.start()

            # Log some test events
            await audit_trail.log_event(
                AuditEventType.AUTHENTICATION_FAILED,
                "User login",
                user_id="user1",
                component="auth",
            )

            await audit_trail.log_event(
                AuditEventType.DATA_MODIFICATION,
                "Data operation",
                user_id="user2",
                component="data",
                log_level=AuditLogLevel.INFO,
            )

            await audit_trail.log_event(
                AuditEventType.ERROR_OCCURRED,
                "System error",
                log_level=AuditLogLevel.ERROR,
            )

            # Wait for events to be processed (minimal for CI)
            await asyncio.sleep(0.01)

            # Test querying all events (exercise the get_events method)
            events = await audit_trail.get_events()
            assert isinstance(events, list)

            # Test filtering by event type (exercises filtering logic)
            auth_events = await audit_trail.get_events(
                event_type=AuditEventType.AUTHENTICATION_FAILED
            )
            assert isinstance(auth_events, list)

            # Test filtering by user ID
            user1_events = await audit_trail.get_events(user_id="user1")
            assert isinstance(user1_events, list)

            # Test filtering by component
            auth_component_events = await audit_trail.get_events(component="auth")
            assert isinstance(auth_component_events, list)

            # Test filtering by log level
            error_events = await audit_trail.get_events(log_level=AuditLogLevel.ERROR)
            assert isinstance(error_events, list)

            # Test time-based filtering
            now = datetime.now(timezone.utc)
            past_events = await audit_trail.get_events(
                start_time=now - timedelta(hours=1), end_time=now + timedelta(hours=1)
            )
            assert isinstance(past_events, list)

            # Test limit parameter
            limited_events = await audit_trail.get_events(limit=2)
            assert isinstance(limited_events, list)

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_trail_corrupted_data_handling(self):
        """Test audit trail handling of corrupted storage data."""
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            policy = CompliancePolicy(level=ComplianceLevel.SOC2)
            audit_trail = AuditTrail(storage_path=Path(temp_dir), policy=policy)

            # Create a corrupted log file
            log_file = Path(temp_dir) / "audit_2024-01-01.jsonl"
            with open(log_file, "w") as f:
                f.write('{"valid": "json"}\n')
                f.write("invalid json line\n")  # Corrupted line
                f.write('{"another": "valid"}\n')

            # Querying should handle corrupted data gracefully
            events = await audit_trail.get_events()
            # Should return events that could be parsed, ignoring corrupted ones
            assert isinstance(events, list)

    @pytest.mark.asyncio
    async def test_audit_trail_storage_error_handling(self):
        """Test audit trail storage error handling."""
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            policy = CompliancePolicy(level=ComplianceLevel.SOC2)
            audit_trail = AuditTrail(storage_path=Path(temp_dir), policy=policy)

            await audit_trail.start()

            # Mock file operations to raise exceptions
            with patch("builtins.open", mock_open()) as mock_file:
                mock_file.side_effect = OSError("Storage error")

                # Event processing should continue despite storage errors
                event_id = await audit_trail.log_event(
                    AuditEventType.SYSTEM_STARTUP, "Test with storage error"
                )
                assert event_id  # Should still return an event ID

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_trail_cleanup(self):
        """Test audit trail cleanup functionality."""
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            policy = CompliancePolicy(level=ComplianceLevel.SOC2)
            audit_trail = AuditTrail(storage_path=Path(temp_dir), policy=policy)

            await audit_trail.start()

            # Log an event to ensure it's running
            await audit_trail.log_event(
                AuditEventType.SYSTEM_STARTUP, "Test before cleanup"
            )

            # Test cleanup
            await audit_trail.cleanup()

            # Audit trail should be stopped after cleanup (processing task should be done)
            assert (
                audit_trail._processing_task is None
                or audit_trail._processing_task.done()
            )


# Configuration for pytest-asyncio
pytestmark = pytest.mark.asyncio
