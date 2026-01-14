"""
Tests for basic audit trail functionality.

Scope:
- Basic audit event logging
- Audit event types and enums
- Compliance policy creation
- Audit trail initialization and lifecycle
- Event logging variations
- Error logging
"""

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from fapilog.core import (
    AuditEventType,
    AuditLogLevel,
    AuditTrail,
    AuthenticationError,
    ComplianceLevel,
    CompliancePolicy,
    ComponentError,
    NetworkError,
    ValidationError,
)


class TestAuditTrailsBasic:
    """Test basic audit trail functionality."""

    @pytest.mark.asyncio
    async def test_audit_trail_basic_logging(self):
        """Test basic audit event logging."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            policy = CompliancePolicy(level=ComplianceLevel.BASIC)
            audit_trail = AuditTrail(policy, storage_path)

            await audit_trail.start()

            # Log an event
            event_id = await audit_trail.log_event(
                AuditEventType.ERROR_OCCURRED,
                "Test error occurred",
                component="test-component",
                user_id="test-user",
            )

            assert event_id is not None
            assert audit_trail._event_count == 1

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_error_logging(self):
        """Test error-specific audit logging."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            audit_trail = AuditTrail(storage_path=storage_path)

            await audit_trail.start()

            # Create a test error
            error = ComponentError("Component failed", component_name="test-component")

            # Audit the error
            event_id = await audit_trail.log_error(error, operation="test_operation")

            assert event_id is not None
            assert audit_trail._error_count == 1

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_security_events(self):
        """Test security event auditing."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            audit_trail = AuditTrail(storage_path=storage_path)

            await audit_trail.start()

            # Log security event
            event_id = await audit_trail.log_security_event(
                AuditEventType.AUTHENTICATION_FAILED,
                "Invalid login attempt",
                user_id="attempted-user",
                client_ip="192.168.1.100",
            )

            assert event_id is not None
            assert audit_trail._security_event_count == 1

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_data_access_logging(self):
        """Test data access audit logging."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            audit_trail = AuditTrail(storage_path=storage_path)

            await audit_trail.start()

            # Log data access
            event_id = await audit_trail.log_data_access(
                resource="sensitive_database",
                operation="read",
                user_id="data-analyst",
                contains_pii=True,
                data_classification="confidential",
            )

            assert event_id is not None

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_compliance_policy_enforcement(self):
        """Test compliance policy enforcement."""
        policy = CompliancePolicy(
            level=ComplianceLevel.GDPR,
            gdpr_data_subject_rights=True,
            real_time_alerts=True,
        )

        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            audit_trail = AuditTrail(policy, storage_path)

            await audit_trail.start()

            # Log PII access (should trigger GDPR compliance)
            await audit_trail.log_event(
                AuditEventType.DATA_ACCESS,
                "PII data accessed",
                contains_pii=True,
                user_id="gdpr-user",
            )

            stats = await audit_trail.get_statistics()
            assert stats["policy"]["compliance_level"] == "gdpr"

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_event_type_enum(self):
        """Test AuditEventType enum values."""
        # Test error events
        assert AuditEventType.ERROR_OCCURRED == "error_occurred"
        assert AuditEventType.ERROR_RECOVERED == "error_recovered"
        assert AuditEventType.ERROR_ESCALATED == "error_escalated"

        # Test security events
        assert AuditEventType.AUTHENTICATION_FAILED == "authentication_failed"
        assert AuditEventType.AUTHORIZATION_FAILED == "authorization_failed"
        assert AuditEventType.SECURITY_VIOLATION == "security_violation"

        # Test system events
        assert AuditEventType.SYSTEM_STARTUP == "system_startup"
        assert AuditEventType.SYSTEM_SHUTDOWN == "system_shutdown"
        assert AuditEventType.COMPONENT_FAILURE == "component_failure"
        assert AuditEventType.COMPONENT_RECOVERY == "component_recovery"

        # Test data events
        assert AuditEventType.DATA_ACCESS == "data_access"
        assert AuditEventType.DATA_MODIFICATION == "data_modification"
        assert AuditEventType.DATA_DELETION == "data_deletion"

    @pytest.mark.asyncio
    async def test_compliance_level_enum(self):
        """Test ComplianceLevel enum values."""
        assert ComplianceLevel.NONE == "none"
        assert ComplianceLevel.BASIC == "basic"
        assert ComplianceLevel.SOX == "sox"
        assert ComplianceLevel.HIPAA == "hipaa"
        assert ComplianceLevel.GDPR == "gdpr"
        assert ComplianceLevel.PCI_DSS == "pci_dss"
        assert ComplianceLevel.SOC2 == "soc2"
        assert ComplianceLevel.ISO27001 == "iso27001"

    @pytest.mark.asyncio
    async def test_audit_log_level_enum(self):
        """Test AuditLogLevel enum values."""

        assert AuditLogLevel.DEBUG == "debug"
        assert AuditLogLevel.INFO == "info"
        assert AuditLogLevel.WARNING == "warning"
        assert AuditLogLevel.ERROR == "error"
        assert AuditLogLevel.CRITICAL == "critical"
        assert AuditLogLevel.SECURITY == "security"

    @pytest.mark.asyncio
    async def test_compliance_policy_creation(self):
        """Test CompliancePolicy model creation and validation."""
        # Test default policy
        policy = CompliancePolicy()
        assert policy.level == ComplianceLevel.BASIC
        assert policy.enabled is True
        assert policy.retention_days == 365
        assert policy.archive_after_days == 90
        assert policy.encrypt_audit_logs is True
        assert policy.require_integrity_check is True
        assert policy.real_time_alerts is True
        assert policy.alert_on_critical_errors is True
        assert policy.alert_on_security_events is True
        assert policy.gdpr_data_subject_rights is False
        assert policy.hipaa_minimum_necessary is False
        assert policy.sox_change_control is False

        # Test custom policy
        custom_policy = CompliancePolicy(
            level=ComplianceLevel.GDPR,
            retention_days=7 * 365,  # 7 years
            archive_after_days=180,
            real_time_alerts=False,
            gdpr_data_subject_rights=True,
            hipaa_minimum_necessary=False,
            sox_change_control=False,
        )
        assert custom_policy.level == ComplianceLevel.GDPR
        assert custom_policy.retention_days == 2555
        assert custom_policy.archive_after_days == 180
        assert custom_policy.real_time_alerts is False
        assert custom_policy.gdpr_data_subject_rights is True
        assert custom_policy.hipaa_minimum_necessary is False
        assert custom_policy.sox_change_control is False

    @pytest.mark.asyncio
    async def test_audit_event_creation(self):
        """Test AuditEvent model creation and validation."""
        # Test basic event
        from fapilog.core.audit import AuditEvent

        event = AuditEvent(
            event_type=AuditEventType.ERROR_OCCURRED,
            message="Test error message",
            component="test-component",
        )
        assert event.event_type == AuditEventType.ERROR_OCCURRED
        assert event.message == "Test error message"
        assert event.component == "test-component"
        assert event.event_id is not None
        assert event.timestamp is not None
        assert event.log_level == AuditLogLevel.INFO  # Default log level

        # Test event with full metadata
        metadata = {
            "operation": "test_operation",
            "duration_ms": 150,
            "request_id": "req-123",
        }
        detailed_event = AuditEvent(
            event_type=AuditEventType.DATA_ACCESS,
            message="Sensitive data accessed",
            component="data-service",
            user_id="user-456",
            session_id="session-789",
            client_ip="192.168.1.100",
            contains_pii=True,
            contains_phi=False,
            data_classification="confidential",
            metadata=metadata,
        )
        assert detailed_event.user_id == "user-456"
        assert detailed_event.contains_pii is True
        assert detailed_event.contains_phi is False
        assert detailed_event.data_classification == "confidential"
        assert detailed_event.metadata["operation"] == "test_operation"

    @pytest.mark.asyncio
    async def test_audit_trail_initialization(self):
        """Test AuditTrail initialization with different configurations."""
        # Test with minimal configuration
        minimal_trail = AuditTrail()
        assert minimal_trail.policy.level == ComplianceLevel.BASIC
        assert minimal_trail.storage_path.name == "audit_logs"  # Default path
        assert minimal_trail._event_count == 0
        assert minimal_trail._error_count == 0
        assert minimal_trail._security_event_count == 0

        # Test with custom configuration
        policy = CompliancePolicy(level=ComplianceLevel.HIPAA, retention_days=10 * 365)
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            configured_trail = AuditTrail(policy=policy, storage_path=storage_path)
            assert configured_trail.policy.level == ComplianceLevel.HIPAA
            assert configured_trail.storage_path == storage_path

    @pytest.mark.asyncio
    async def test_audit_trail_lifecycle(self):
        """Test AuditTrail start/stop lifecycle."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            audit_trail = AuditTrail(storage_path=storage_path)

            # Test start and stop (simplified)
            await audit_trail.start()
            # No public _running attribute, just test that start/stop work
            await audit_trail.stop()

            # Test multiple start/stop calls (should be idempotent)
            await audit_trail.start()
            await audit_trail.start()  # Should be idempotent
            await audit_trail.stop()
            await audit_trail.stop()  # Should be idempotent

    @pytest.mark.asyncio
    async def test_audit_trail_event_logging_variations(self):
        """Test different ways of logging events."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            audit_trail = AuditTrail(storage_path=storage_path)
            await audit_trail.start()

            # Test basic event logging
            event_id_1 = await audit_trail.log_event(
                AuditEventType.SYSTEM_STARTUP, "System initialized"
            )
            assert event_id_1 is not None

            # Test event with all optional parameters
            event_id_2 = await audit_trail.log_event(
                AuditEventType.DATA_MODIFICATION,
                "User profile updated",
                component="user-service",
                user_id="user-123",
                session_id="session-456",
                client_ip="10.0.0.1",
                contains_pii=True,
                contains_phi=False,
                data_classification="personal",
                metadata={"field": "email", "old_value": "old@example.com"},
            )
            assert event_id_2 is not None
            assert event_id_1 != event_id_2

            # Test event with custom metadata only
            event_id_3 = await audit_trail.log_event(
                AuditEventType.COMPONENT_RECOVERY,
                "Component recovered successfully",
                component="recovery-service",
            )
            assert event_id_3 is not None

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_trail_error_logging_comprehensive(self):
        """Test comprehensive error logging functionality."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            audit_trail = AuditTrail(storage_path=storage_path)
            await audit_trail.start()

            # Test different error types
            validation_error = ValidationError("Invalid input data", field_name="email")
            event_id_1 = await audit_trail.log_error(
                validation_error, operation="user_registration"
            )
            assert event_id_1 is not None

            auth_error = AuthenticationError(
                "Invalid credentials", user_id="failed-user"
            )
            event_id_2 = await audit_trail.log_error(
                auth_error, operation="login_attempt"
            )
            assert event_id_2 is not None

            network_error = NetworkError(
                "Connection timeout", service_name="external-api"
            )
            event_id_3 = await audit_trail.log_error(
                network_error, operation="api_call"
            )
            assert event_id_3 is not None

            # Check error count
            assert audit_trail._error_count == 3

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_trail_security_event_logging(self):
        """Test comprehensive security event logging."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            audit_trail = AuditTrail(storage_path=storage_path)
            await audit_trail.start()

            # Test authentication failure
            auth_event_id = await audit_trail.log_security_event(
                AuditEventType.AUTHENTICATION_FAILED,
                "Multiple failed login attempts",
                user_id="suspicious-user",
                client_ip="192.168.1.100",
                additional_context={"attempt_count": 5, "time_window": "5_minutes"},
            )
            assert auth_event_id is not None

            # Test authorization failure
            authz_event_id = await audit_trail.log_security_event(
                AuditEventType.AUTHORIZATION_FAILED,
                "Access denied to restricted resource",
                user_id="limited-user",
                client_ip="10.0.0.50",
                additional_context={
                    "resource": "/admin/users",
                    "required_role": "admin",
                },
            )
            assert authz_event_id is not None

            # Test security violation
            violation_event_id = await audit_trail.log_security_event(
                AuditEventType.SECURITY_VIOLATION,
                "Potential SQL injection attempt",
                user_id="attacker",
                client_ip="203.0.113.1",
                additional_context={
                    "payload": "'; DROP TABLE users; --",
                    "blocked": True,
                },
            )
            assert violation_event_id is not None

            # Check security event count
            assert audit_trail._security_event_count == 3

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_trail_data_access_comprehensive(self):
        """Test comprehensive data access logging."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            audit_trail = AuditTrail(storage_path=storage_path)
            await audit_trail.start()

            # Test PII data access
            pii_event_id = await audit_trail.log_data_access(
                resource="customer_database",
                operation="select",
                user_id="data-analyst",
                contains_pii=True,
                contains_phi=False,
                data_classification="confidential",
                record_count=150,
                additional_metadata={
                    "query": "SELECT * FROM customers WHERE region='EU'"
                },
            )
            assert pii_event_id is not None

            # Test PHI data access
            phi_event_id = await audit_trail.log_data_access(
                resource="medical_records",
                operation="read",
                user_id="doctor-smith",
                contains_pii=True,
                contains_phi=True,
                data_classification="restricted",
                record_count=1,
                additional_metadata={
                    "patient_id": "PAT-12345",
                    "diagnosis_code": "ICD-10",
                },
            )
            assert phi_event_id is not None

            # Test data modification
            modify_event_id = await audit_trail.log_data_access(
                resource="user_profiles",
                operation="update",
                user_id="user-456",
                contains_pii=True,
                data_classification="personal",
                record_count=1,
                additional_metadata={
                    "fields_modified": ["email", "phone"],
                    "reason": "user_request",
                },
            )
            assert modify_event_id is not None

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_trail_statistics(self):
        """Test audit trail statistics functionality."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            policy = CompliancePolicy(level=ComplianceLevel.SOC2)
            audit_trail = AuditTrail(policy=policy, storage_path=storage_path)
            await audit_trail.start()

            # Generate various events
            await audit_trail.log_event(AuditEventType.SYSTEM_STARTUP, "System started")
            await audit_trail.log_error(
                ComponentError("Test error", component_name="test")
            )
            await audit_trail.log_security_event(
                AuditEventType.AUTHENTICATION_FAILED,
                "Login failed",
                user_id="test-user",
            )
            await audit_trail.log_data_access(
                resource="test_db",
                operation="read",
                user_id="analyst",
                contains_pii=True,
            )

            # Get statistics
            stats = await audit_trail.get_statistics()

            # Verify statistics structure and values (adjust based on actual structure)
            assert "policy" in stats
            assert "error_events" in stats
            assert "security_events" in stats

            assert stats["error_events"] == 1
            assert stats["security_events"] == 1
            assert stats["policy"]["compliance_level"] == "soc2"
            assert stats["policy"]["retention_days"] == 365

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_trail_buffer_management(self):
        """Test audit trail buffer management and flushing."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            # Configure basic audit trail for testing
            audit_trail = AuditTrail(storage_path=storage_path)
            await audit_trail.start()

            # Add events to fill buffer
            for i in range(5):
                await audit_trail.log_event(
                    AuditEventType.DATA_ACCESS, f"Access event {i}", user_id=f"user-{i}"
                )

            # Allow some time for background flushing (reduced for CI)
            await asyncio.sleep(0.05)

            # Check that events were processed
            assert audit_trail._event_count == 5

            # Just check that events were processed (no manual flush needed)

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_trail_storage_file_operations(self):
        """Test audit trail file storage operations."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            audit_trail = AuditTrail(storage_path=storage_path)
            await audit_trail.start()

            # Log some events
            await audit_trail.log_event(AuditEventType.SYSTEM_STARTUP, "System started")
            await audit_trail.log_error(
                ComponentError("Test error", component_name="test")
            )

            # Allow time for automatic flushing (reduced for CI)
            await asyncio.sleep(0.05)

            # Check that files were created
            assert storage_path.exists()
            audit_files = list(storage_path.glob("audit_*.jsonl"))
            assert len(audit_files) > 0

            # Verify file content
            with open(audit_files[0]) as f:
                lines = f.readlines()
                assert len(lines) >= 2

                # Parse and verify first event
                first_event = json.loads(lines[0])
                assert first_event["event_type"] == "system_startup"
                assert first_event["message"] == "System started"

            await audit_trail.stop()


# Configuration for pytest-asyncio
pytestmark = pytest.mark.asyncio
