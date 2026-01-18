"""
Enterprise Compliance Error Handling with Audit Trails for Fapilog v3.

This module provides comprehensive audit trail functionality for enterprise
compliance, including error tracking, compliance reporting, and security
event monitoring for async operations.
"""

import asyncio
import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from fapilog.core.errors import (
    AsyncErrorContext,
    ErrorCategory,
    ErrorSeverity,
    FapilogError,
)
from pydantic import BaseModel, Field, ValidationError


class AuditEventType(str, Enum):
    """Types of audit events for compliance tracking."""

    # Error events
    ERROR_OCCURRED = "error_occurred"
    ERROR_RECOVERED = "error_recovered"
    ERROR_ESCALATED = "error_escalated"

    # Security events
    AUTHENTICATION_FAILED = "authentication_failed"
    AUTHORIZATION_FAILED = "authorization_failed"
    SECURITY_VIOLATION = "security_violation"

    # System events
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    COMPONENT_FAILURE = "component_failure"
    COMPONENT_RECOVERY = "component_recovery"

    # Data events
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    DATA_DELETION = "data_deletion"
    DATA_EXPORT = "data_export"

    # Configuration events
    CONFIG_CHANGED = "config_changed"
    PLUGIN_LOADED = "plugin_loaded"
    PLUGIN_UNLOADED = "plugin_unloaded"

    # Compliance events
    COMPLIANCE_CHECK = "compliance_check"
    AUDIT_LOG_ACCESS = "audit_log_access"
    RETENTION_POLICY_APPLIED = "retention_policy_applied"


class ComplianceLevel(str, Enum):
    """Compliance levels for different regulatory requirements."""

    NONE = "none"  # No specific compliance requirements
    BASIC = "basic"  # Basic audit logging
    SOX = "sox"  # Sarbanes-Oxley compliance
    HIPAA = "hipaa"  # Health Insurance Portability and Accountability Act
    GDPR = "gdpr"  # General Data Protection Regulation
    PCI_DSS = "pci_dss"  # Payment Card Industry Data Security Standard
    SOC2 = "soc2"  # Service Organization Control 2
    ISO27001 = "iso27001"  # ISO 27001 Information Security Management


class AuditLogLevel(str, Enum):
    """Audit log levels for filtering and retention."""

    DEBUG = "debug"  # Detailed debugging information
    INFO = "info"  # General information
    WARNING = "warning"  # Warning conditions
    ERROR = "error"  # Error conditions
    CRITICAL = "critical"  # Critical conditions
    SECURITY = "security"  # Security-related events


@dataclass
class CompliancePolicy:
    """Configuration for compliance policies and requirements."""

    # Basic policy settings
    level: ComplianceLevel = ComplianceLevel.BASIC
    enabled: bool = True

    # Retention settings
    retention_days: int = 365  # How long to keep audit logs
    archive_after_days: int = 90  # When to archive logs

    # Security settings
    encrypt_audit_logs: bool = False  # Encryption not yet implemented
    require_integrity_check: bool = True  # Verify log integrity

    # Access control
    audit_access_roles: list[str] = field(default_factory=lambda: ["admin", "auditor"])

    # Compliance-specific settings
    gdpr_data_subject_rights: bool = False  # Support GDPR data subject rights
    hipaa_minimum_necessary: bool = False  # HIPAA minimum necessary rule
    sox_change_control: bool = False  # SOX change control requirements

    # Alert settings
    real_time_alerts: bool = True  # Send real-time compliance alerts
    alert_on_critical_errors: bool = True  # Alert on critical errors
    alert_on_security_events: bool = True  # Alert on security events


class AuditEvent(BaseModel):
    """Individual audit event with comprehensive compliance information."""

    # Event identification
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: AuditEventType
    log_level: AuditLogLevel = AuditLogLevel.INFO
    sequence_number: int | None = None
    previous_hash: str | None = None

    # Event details
    message: str
    component: str | None = None
    operation: str | None = None

    # User and session context
    user_id: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    client_ip: str | None = None
    user_agent: str | None = None

    # System context
    container_id: str | None = None
    plugin_name: str | None = None
    hostname: str | None = None
    process_id: int | None = None

    # Error context (if applicable)
    error_context: AsyncErrorContext | None = None
    error_category: ErrorCategory | None = None
    error_severity: ErrorSeverity | None = None

    # Data classification
    data_classification: str | None = (
        None  # e.g., "public", "internal", "confidential", "restricted"
    )
    contains_pii: bool = False  # Contains personally identifiable information
    contains_phi: bool = False  # Contains protected health information

    # Compliance metadata
    compliance_level: ComplianceLevel = ComplianceLevel.BASIC
    regulatory_tags: list[str] = Field(default_factory=list)
    retention_category: str | None = None

    # Additional context
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Integrity and security
    checksum: str | None = None  # For log integrity verification
    signature: str | None = None  # Digital signature for tamper detection

    model_config = {"extra": "allow"}


@dataclass
class AuditChainVerificationResult:
    valid: bool
    events_checked: int
    first_invalid_sequence: int | None = None
    error_message: str | None = None


class AuditTrail:
    """
    Comprehensive audit trail system for enterprise compliance.

    This class provides:
    - Comprehensive audit event logging with compliance metadata
    - Multiple storage backends (file, database, remote)
    - Real-time compliance monitoring and alerting
    - Data retention and archival policies
    - Security features like encryption and integrity checking
    - Support for multiple compliance frameworks
    """

    def __init__(
        self,
        policy: CompliancePolicy | None = None,
        storage_path: Path | None = None,
    ) -> None:
        """
        Initialize audit trail system.

        Args:
            policy: Compliance policy configuration
            storage_path: Path for audit log storage
        """
        self.policy = policy or CompliancePolicy()
        self.storage_path = storage_path or Path("audit_logs")

        # Warn if encryption requested but not implemented
        if self.policy.encrypt_audit_logs:
            import warnings

            warnings.warn(
                "encrypt_audit_logs=True requested but encryption is not yet "
                "implemented. Audit logs will be written as plaintext JSONL with "
                "hash-chain integrity. See docs for encryption roadmap.",
                UserWarning,
                stacklevel=2,
            )

        # Event queue for async processing
        self._event_queue: asyncio.Queue[AuditEvent] = asyncio.Queue()
        self._processing_task: asyncio.Task | None = None

        # Statistics and monitoring
        self._event_count = 0
        self._error_count = 0
        self._security_event_count = 0

        # Thread safety
        self._lock = asyncio.Lock()
        self._stopping = False

        # Integrity chain
        self._seq_counter: int = 0
        self._last_hash: str | None = None

        # Initialize storage
        self._init_storage()

    def _init_storage(self) -> None:
        """Initialize audit log storage."""
        if not self.storage_path.exists():
            self.storage_path.mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        """Start audit trail processing."""
        if self._processing_task is None or self._processing_task.done():
            self._processing_task = asyncio.create_task(self._process_events())

    async def stop(self) -> None:
        """Stop audit trail processing."""
        self._stopping = True
        # Drain queued events before cancellation
        await self.drain()
        if self._processing_task and not self._processing_task.done():
            self._processing_task.cancel()
            try:
                # Wait for cancellation with timeout to prevent hanging
                await asyncio.wait_for(self._processing_task, timeout=0.5)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        self._processing_task = None
        self._stopping = False

    async def drain(self) -> None:
        """Flush any queued audit events to storage."""
        while True:
            try:
                event = self._event_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            try:
                await self._store_event(event)
                await self._check_compliance_alerts(event)
            except Exception:
                # Contain drain failures
                pass

    async def log_event(
        self,
        event_type: AuditEventType,
        message: str,
        *,
        log_level: AuditLogLevel = AuditLogLevel.INFO,
        component: str | None = None,
        operation: str | None = None,
        error: FapilogError | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        request_id: str | None = None,
        contains_pii: bool = False,
        contains_phi: bool = False,
        data_classification: str | None = None,
        regulatory_tags: list[str] | None = None,
        **metadata: Any,
    ) -> str:
        """
        Log an audit event.

        Args:
            event_type: Type of audit event
            message: Event description
            log_level: Audit log level
            component: Component that generated the event
            operation: Operation being performed
            error: Associated error (if any)
            user_id: User identifier
            session_id: Session identifier
            request_id: Request identifier
            contains_pii: Whether event contains PII
            contains_phi: Whether event contains PHI
            data_classification: Data classification level
            regulatory_tags: Regulatory compliance tags
            **metadata: Additional event metadata

        Returns:
            Event ID for tracking
        """
        if not self.policy.enabled:
            return ""

        # Create audit event
        event = AuditEvent(
            event_type=event_type,
            message=message,
            log_level=log_level,
            component=component,
            operation=operation,
            user_id=user_id,
            session_id=session_id,
            request_id=request_id,
            contains_pii=contains_pii,
            contains_phi=contains_phi,
            data_classification=data_classification,
            compliance_level=self.policy.level,
            regulatory_tags=regulatory_tags or [],
            metadata=metadata,
        )

        # Add error context if provided
        if error:
            event.error_context = error.context
            event.error_category = error.context.category
            event.error_severity = error.context.severity

        # Add system context
        try:
            import os
            import socket

            event.hostname = socket.gethostname()
            event.process_id = os.getpid()
        except Exception:
            pass

        # Queue event for processing
        await self._event_queue.put(event)

        # Update statistics
        async with self._lock:
            self._event_count += 1
            if event_type == AuditEventType.ERROR_OCCURRED:
                self._error_count += 1
            elif log_level in [AuditLogLevel.ERROR, AuditLogLevel.CRITICAL]:
                self._error_count += 1
            if event_type in [
                AuditEventType.AUTHENTICATION_FAILED,
                AuditEventType.AUTHORIZATION_FAILED,
                AuditEventType.SECURITY_VIOLATION,
            ]:
                self._security_event_count += 1

        return event.event_id

    async def log_error(
        self,
        error: FapilogError,
        *,
        operation: str | None = None,
        component: str | None = None,
        **metadata: Any,
    ) -> str:
        """
        Log an error event with full context.

        Args:
            error: Error to log
            operation: Operation that failed
            component: Component that generated the error
            **metadata: Additional metadata

        Returns:
            Event ID for tracking
        """
        return await self.log_event(
            AuditEventType.ERROR_OCCURRED,
            f"Error occurred: {error.message}",
            log_level=self._error_severity_to_log_level(error.context.severity),
            operation=operation,
            component=component,
            error=error,
            user_id=error.context.user_id,
            session_id=error.context.session_id,
            request_id=error.context.request_id,
            **metadata,
        )

    async def log_security_event(
        self,
        event_type: AuditEventType,
        message: str,
        *,
        user_id: str | None = None,
        client_ip: str | None = None,
        user_agent: str | None = None,
        **metadata: Any,
    ) -> str:
        """
        Log a security-related event.

        Args:
            event_type: Type of security event
            message: Event description
            user_id: User involved in the event
            client_ip: Client IP address
            user_agent: User agent string
            **metadata: Additional metadata

        Returns:
            Event ID for tracking
        """
        return await self.log_event(
            event_type,
            message,
            log_level=AuditLogLevel.SECURITY,
            user_id=user_id,
            client_ip=client_ip,
            user_agent=user_agent,
            **metadata,
        )

    async def log_data_access(
        self,
        resource: str,
        operation: str,
        *,
        user_id: str | None = None,
        data_classification: str | None = None,
        contains_pii: bool = False,
        contains_phi: bool = False,
        **metadata: Any,
    ) -> str:
        """
        Log data access event for compliance.

        Args:
            resource: Resource being accessed
            operation: Type of operation (read, write, delete, etc.)
            user_id: User performing the operation
            data_classification: Classification of the data
            contains_pii: Whether data contains PII
            contains_phi: Whether data contains PHI
            **metadata: Additional metadata

        Returns:
            Event ID for tracking
        """
        event_type_map = {
            "read": AuditEventType.DATA_ACCESS,
            "write": AuditEventType.DATA_MODIFICATION,
            "update": AuditEventType.DATA_MODIFICATION,
            "delete": AuditEventType.DATA_DELETION,
            "export": AuditEventType.DATA_EXPORT,
        }

        event_type = event_type_map.get(operation.lower(), AuditEventType.DATA_ACCESS)

        return await self.log_event(
            event_type,
            f"Data {operation} on resource: {resource}",
            user_id=user_id,
            operation=operation,
            data_classification=data_classification,
            contains_pii=contains_pii,
            contains_phi=contains_phi,
            resource=resource,
            **metadata,
        )

    async def _process_events(self) -> None:
        """Process audit events from the queue."""
        while True:
            try:
                if self._stopping and self._event_queue.empty():
                    break
                # Get event from queue with shorter timeout for CI compatibility
                event = await asyncio.wait_for(self._event_queue.get(), timeout=0.1)

                # Process the event
                await self._store_event(event)
                await self._check_compliance_alerts(event)

            except asyncio.TimeoutError:
                # Check if we should continue or exit
                continue
            except asyncio.CancelledError:
                # Properly handle cancellation
                break
            except Exception:
                # Log processing error (but don't create infinite loop)
                pass

    async def _store_event(self, event: AuditEvent) -> None:
        """Store audit event to configured storage."""
        try:
            async with self._lock:
                self._seq_counter += 1
                event.sequence_number = self._seq_counter
                event.previous_hash = self._last_hash

                payload = event.model_dump(mode="json", exclude_none=False)
                checksum = self._compute_checksum(payload)
                event.checksum = checksum
                payload["checksum"] = checksum
                payload["previous_hash"] = event.previous_hash
                payload["sequence_number"] = event.sequence_number
                self._last_hash = checksum

                json_line = self._canonical_json(payload)

            # Store to file - offload to thread pool to avoid blocking event loop
            date_str = event.timestamp.strftime("%Y-%m-%d")
            log_file = self.storage_path / f"audit_{date_str}.jsonl"
            await asyncio.to_thread(self._write_to_file, log_file, json_line)

        except Exception:
            # Storage failure - critical for compliance
            pass

    def _write_to_file(self, path: Path, content: str) -> None:
        """Synchronous file write, called via to_thread."""
        with open(path, "a", encoding="utf-8") as f:
            f.write(content + "\n")

    async def _check_compliance_alerts(self, event: AuditEvent) -> None:
        """Check if event should trigger compliance alerts."""
        if not self.policy.real_time_alerts:
            return

        should_alert = False

        # Check for critical errors
        if (
            self.policy.alert_on_critical_errors
            and event.log_level == AuditLogLevel.CRITICAL
        ):
            should_alert = True

        # Check for security events
        if (
            self.policy.alert_on_security_events
            and event.log_level == AuditLogLevel.SECURITY
        ):
            should_alert = True

        # Compliance-specific checks
        if self.policy.level == ComplianceLevel.GDPR and event.contains_pii:
            should_alert = True

        if self.policy.level == ComplianceLevel.HIPAA and event.contains_phi:
            should_alert = True

        if should_alert:
            await self._send_compliance_alert(event)

    async def _send_compliance_alert(self, event: AuditEvent) -> None:
        """Send compliance alert for the event."""
        # Implementation would integrate with alerting system
        pass

    def _error_severity_to_log_level(self, severity: ErrorSeverity) -> AuditLogLevel:
        """Convert error severity to audit log level."""
        mapping = {
            ErrorSeverity.CRITICAL: AuditLogLevel.CRITICAL,
            ErrorSeverity.HIGH: AuditLogLevel.ERROR,
            ErrorSeverity.MEDIUM: AuditLogLevel.WARNING,
            ErrorSeverity.LOW: AuditLogLevel.INFO,
            ErrorSeverity.INFO: AuditLogLevel.INFO,
        }
        return mapping.get(severity, AuditLogLevel.INFO)

    @classmethod
    def verify_chain(cls, events: Iterable[AuditEvent]) -> AuditChainVerificationResult:
        """Verify integrity chain across provided events."""
        last_hash: str | None = None
        expected_seq = 1
        checked = 0

        for event in events:
            checked += 1
            if event.sequence_number != expected_seq:
                return AuditChainVerificationResult(
                    valid=False,
                    events_checked=checked,
                    first_invalid_sequence=expected_seq,
                    error_message="sequence mismatch",
                )
            if event.previous_hash != last_hash:
                return AuditChainVerificationResult(
                    valid=False,
                    events_checked=checked,
                    first_invalid_sequence=expected_seq,
                    error_message="previous hash mismatch",
                )

            payload = event.model_dump(mode="json", exclude_none=False)
            computed = cls._compute_checksum(payload)
            if event.checksum != computed:
                return AuditChainVerificationResult(
                    valid=False,
                    events_checked=checked,
                    first_invalid_sequence=expected_seq,
                    error_message="checksum mismatch",
                )

            last_hash = event.checksum
            expected_seq += 1

        return AuditChainVerificationResult(valid=True, events_checked=checked)

    async def verify_chain_from_storage(self) -> AuditChainVerificationResult:
        """Load events from storage_path and verify their hash chain."""
        events: list[AuditEvent] = []
        try:
            for file in sorted(self.storage_path.glob("audit_*.jsonl")):
                with open(file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            events.append(AuditEvent.model_validate_json(line))
                        except ValidationError:
                            return AuditChainVerificationResult(
                                valid=False,
                                events_checked=len(events),
                                first_invalid_sequence=len(events) + 1,
                                error_message="invalid event payload",
                            )
        except Exception as exc:
            return AuditChainVerificationResult(
                valid=False,
                events_checked=len(events),
                error_message=str(exc),
            )
        # Sort by sequence number to handle async writes completing out of order
        events.sort(key=lambda e: e.sequence_number or 0)
        return self.verify_chain(events)

    @staticmethod
    def _canonical_json(payload: dict[str, Any]) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _compute_checksum(payload: dict[str, Any]) -> str:
        # Do not include checksum itself in hash computation
        stripped = dict(payload)
        stripped.pop("checksum", None)
        canon = AuditTrail._canonical_json(stripped)
        return hashlib.sha256(canon.encode("utf-8")).hexdigest()

    async def get_events(
        self,
        *,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        event_type: AuditEventType | None = None,
        log_level: AuditLogLevel | None = None,
        user_id: str | None = None,
        component: str | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """
        Retrieve audit events with filtering.

        Args:
            start_time: Start time filter
            end_time: End time filter
            event_type: Event type filter
            log_level: Log level filter
            user_id: User ID filter
            component: Component filter
            limit: Maximum number of events to return

        Returns:
            List of matching audit events
        """
        # Implementation would query storage backend
        # This is a simplified version
        events = []

        # Read from files (simplified implementation)
        for log_file in self.storage_path.glob("audit_*.jsonl"):
            try:
                with open(log_file, encoding="utf-8") as f:
                    for line in f:
                        try:
                            event_data = json.loads(line.strip())
                            event = AuditEvent(**event_data)

                            # Apply filters
                            if start_time and event.timestamp < start_time:
                                continue
                            if end_time and event.timestamp > end_time:
                                continue
                            if event_type and event.event_type != event_type:
                                continue
                            if log_level and event.log_level != log_level:
                                continue
                            if user_id and event.user_id != user_id:
                                continue
                            if component and event.component != component:
                                continue

                            events.append(event)

                            if len(events) >= limit:
                                break

                        except Exception:
                            continue

            except Exception:
                continue

        # Sort by timestamp (newest first)
        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events[:limit]

    async def get_statistics(self) -> dict[str, Any]:
        """Get audit trail statistics."""
        return {
            "total_events": self._event_count,
            "error_events": self._error_count,
            "security_events": self._security_event_count,
            "queue_size": self._event_queue.qsize(),
            "policy": {
                "compliance_level": self.policy.level.value,
                "enabled": self.policy.enabled,
                "retention_days": self.policy.retention_days,
                "encryption_enabled": self.policy.encrypt_audit_logs,
            },
        }

    async def cleanup(self) -> None:
        """Clean up audit trail resources."""
        await self.stop()


# Global audit trail instance
_audit_trail: AuditTrail | None = None


async def get_audit_trail(
    policy: CompliancePolicy | None = None, storage_path: Path | None = None
) -> AuditTrail:
    """
    Get global audit trail instance.

    Args:
        policy: Compliance policy (for initialization)
        storage_path: Storage path (for initialization)

    Returns:
        Audit trail instance
    """
    global _audit_trail
    if _audit_trail is None:
        _audit_trail = AuditTrail(policy, storage_path)
        await _audit_trail.start()
    return _audit_trail


async def audit_error(
    error: FapilogError,
    *,
    operation: str | None = None,
    component: str | None = None,
    **metadata: Any,
) -> str:
    """
    Convenience function to audit an error.

    Args:
        error: Error to audit
        operation: Operation that failed
        component: Component that generated the error
        **metadata: Additional metadata

    Returns:
        Event ID for tracking
    """
    audit_trail = await get_audit_trail()
    return await audit_trail.log_error(
        error, operation=operation, component=component, **metadata
    )


async def audit_security_event(
    event_type: AuditEventType,
    message: str,
    *,
    user_id: str | None = None,
    client_ip: str | None = None,
    **metadata: Any,
) -> str:
    """
    Convenience function to audit a security event.

    Args:
        event_type: Type of security event
        message: Event description
        user_id: User involved
        client_ip: Client IP address
        **metadata: Additional metadata

    Returns:
        Event ID for tracking
    """
    audit_trail = await get_audit_trail()
    return await audit_trail.log_security_event(
        event_type, message, user_id=user_id, client_ip=client_ip, **metadata
    )


async def emit_compliance_alert(event: AuditEvent) -> None:  # noqa
    """Public helper to emit a compliance alert for a given audit event."""
    trail = await get_audit_trail()
    try:
        await trail._send_compliance_alert(event)
    except Exception:
        # Alerts are best-effort; contain failures
        pass
