"""Tests verifying audit functionality has been extracted to separate package.

Story 4.44: Extract Audit/Tamper to Separate Package

These tests ensure that:
- Core fapilog works without audit code
- Audit sink is not in the built-in registry
- Old imports fail with clear errors
"""

from __future__ import annotations

import pytest


def test_audit_sink_not_in_built_in_registry() -> None:
    """Audit sink should not be registered as a built-in plugin.

    Note: If fapilog-audit is installed, it will be discoverable via entry point,
    but should NOT be in the built-in registry itself.
    """
    # Access the internal built-in registry directly
    from fapilog.plugins.loader import BUILTIN_SINKS

    assert "audit" not in BUILTIN_SINKS


def test_core_import_does_not_include_audit() -> None:
    """Core module should not export audit-related symbols."""
    from fapilog import core

    # These should not exist in core anymore
    assert not hasattr(core, "AuditTrail")
    assert not hasattr(core, "AuditEvent")
    assert not hasattr(core, "AuditEventType")
    assert not hasattr(core, "ComplianceLevel")
    assert not hasattr(core, "CompliancePolicy")
    assert not hasattr(core, "audit_error")
    assert not hasattr(core, "audit_security_event")
    assert not hasattr(core, "get_audit_trail")

    # Compliance validation should not exist
    assert not hasattr(core, "AuditConfig")
    assert not hasattr(core, "DataHandlingSettings")
    assert not hasattr(core, "validate_compliance_policy")
    assert not hasattr(core, "validate_data_handling")
    assert not hasattr(core, "validate_audit_config")


def test_settings_do_not_have_audit_config() -> None:
    """Settings should not have audit sink configuration."""
    from fapilog import Settings

    settings = Settings()
    # sink_config should not have audit field
    assert not hasattr(settings.sink_config, "audit")


def test_old_audit_imports_fail() -> None:
    """Old audit imports from fapilog.core should fail."""
    with pytest.raises(ImportError):
        from fapilog.core.audit import AuditTrail  # noqa: F401

    with pytest.raises(ImportError):
        from fapilog.core.compliance import (  # noqa: F401
            validate_compliance_policy,
        )

    with pytest.raises(ImportError):
        from fapilog.plugins.sinks.audit import AuditSink  # noqa: F401
