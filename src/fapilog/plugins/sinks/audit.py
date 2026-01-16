from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...core.audit import (
    AuditEventType,
    AuditLogLevel,
    AuditTrail,
    ComplianceLevel,
    CompliancePolicy,
)
from ...core.errors import SinkWriteError


@dataclass
class AuditSinkConfig:
    """Configuration for the audit compliance sink."""

    compliance_level: str = "basic"
    storage_path: str = "audit_logs"
    retention_days: int = 365
    encrypt_logs: bool = False
    require_integrity: bool = True
    real_time_alerts: bool = False


class AuditSink:
    """Sink that writes log entries to the compliance AuditTrail."""

    name = "audit"

    def __init__(self, config: AuditSinkConfig | None = None) -> None:
        self._config = config or AuditSinkConfig()
        self._trail: AuditTrail | None = None

    async def start(self) -> None:
        if self._trail is not None:
            return
        level_value = str(self._config.compliance_level).lower()
        try:
            level = ComplianceLevel(level_value)
        except ValueError:
            level = ComplianceLevel.BASIC
        policy = CompliancePolicy(
            level=level,
            retention_days=self._config.retention_days,
            encrypt_audit_logs=self._config.encrypt_logs,
            require_integrity_check=self._config.require_integrity,
            real_time_alerts=self._config.real_time_alerts,
        )
        self._trail = AuditTrail(policy, Path(self._config.storage_path))
        await self._trail.start()

    async def stop(self) -> None:
        if self._trail is None:
            return
        try:
            await self._trail.stop()
        except Exception:
            # Contain stop failures
            pass

    async def health_check(self) -> bool:
        """Return True if the sink is healthy and ready to write."""
        if self._trail is None:
            return False
        try:
            await self._trail.get_statistics()
            return True
        except Exception:
            return False

    def _resolve_event_type(
        self, entry: dict[str, Any], metadata: dict[str, Any]
    ) -> AuditEventType:
        for key in ("audit_event_type", "event_type"):
            raw = metadata.get(key) or entry.get(key)
            if raw:
                try:
                    return AuditEventType(str(raw))
                except ValueError:
                    pass
        level = str(entry.get("level", "")).upper()
        if level in {"ERROR", "CRITICAL"}:
            return AuditEventType.ERROR_OCCURRED
        if level in {"WARNING"}:
            return AuditEventType.COMPLIANCE_CHECK
        return AuditEventType.DATA_ACCESS

    def _resolve_log_level(self, level: Any) -> AuditLogLevel:
        normalized = str(level or "info").lower()
        mapping = {
            "debug": AuditLogLevel.DEBUG,
            "info": AuditLogLevel.INFO,
            "warning": AuditLogLevel.WARNING,
            "error": AuditLogLevel.ERROR,
            "critical": AuditLogLevel.CRITICAL,
            "security": AuditLogLevel.SECURITY,
        }
        return mapping.get(normalized, AuditLogLevel.INFO)

    async def write(self, entry: dict[str, Any]) -> None:
        trail = self._trail
        if trail is None:
            return
        metadata = entry.get("metadata") or {}
        event_type = self._resolve_event_type(entry, metadata)
        audit_level = self._resolve_log_level(entry.get("level"))
        try:
            await trail.log_event(
                event_type,
                entry.get("message", ""),
                log_level=audit_level,
                component=entry.get("logger"),
                operation=metadata.get("operation"),
                user_id=metadata.get("user_id"),
                session_id=metadata.get("session_id"),
                request_id=entry.get("correlation_id") or metadata.get("request_id"),
                contains_pii=bool(metadata.get("contains_pii", False)),
                contains_phi=bool(metadata.get("contains_phi", False)),
                data_classification=metadata.get("data_classification"),
                regulatory_tags=metadata.get("regulatory_tags"),
                **{
                    k: v
                    for k, v in metadata.items()
                    if k
                    not in {
                        "operation",
                        "user_id",
                        "session_id",
                        "request_id",
                        "contains_pii",
                        "contains_phi",
                        "data_classification",
                        "regulatory_tags",
                        "audit_event_type",
                        "event_type",
                    }
                },
            )
        except Exception as e:
            raise SinkWriteError(
                f"Failed to write to {self.name}",
                sink_name=self.name,
                cause=e,
            ) from e


PLUGIN_METADATA = {
    "name": "audit",
    "version": "1.0.0",
    "plugin_type": "sink",
    "entry_point": "fapilog.plugins.sinks.audit:AuditSink",
    "description": "Writes log entries to compliance audit trail with hash-chain integrity.",
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "0.4.0"},
    "api_version": "1.0",
    "dependencies": [],
}
