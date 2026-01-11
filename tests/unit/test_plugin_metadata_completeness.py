"""
TDD tests for Story 4.23: Complete Plugin Metadata for All Built-in Plugins.

These tests verify all built-in plugins have complete PLUGIN_METADATA.
"""

from __future__ import annotations

import importlib
from typing import Any

import pytest

# All built-in plugin modules that should have PLUGIN_METADATA
BUILTIN_PLUGIN_MODULES = [
    # Sinks
    "fapilog.plugins.sinks.stdout_json",
    "fapilog.plugins.sinks.stdout_pretty",
    "fapilog.plugins.sinks.rotating_file",
    "fapilog.plugins.sinks.http_client",
    "fapilog.plugins.sinks.webhook",
    "fapilog.plugins.sinks.contrib.loki",
    "fapilog.plugins.sinks.contrib.cloudwatch",
    # Enrichers
    "fapilog.plugins.enrichers.runtime_info",
    "fapilog.plugins.enrichers.context_vars",
    "fapilog.plugins.enrichers.kubernetes",
    # Redactors
    "fapilog.plugins.redactors.field_mask",
    "fapilog.plugins.redactors.regex_mask",
    "fapilog.plugins.redactors.url_credentials",
    # Processors
    "fapilog.plugins.processors.zero_copy",
    "fapilog.plugins.processors.size_guard",
]

REQUIRED_FIELDS = {
    "name",
    "version",
    "plugin_type",
    "entry_point",
    "description",
    "author",
    "compatibility",
    "api_version",
}


@pytest.mark.parametrize("module_path", BUILTIN_PLUGIN_MODULES)
def test_plugin_has_metadata(module_path: str) -> None:
    """Each plugin module must export PLUGIN_METADATA."""
    module = importlib.import_module(module_path)
    assert hasattr(module, "PLUGIN_METADATA"), f"{module_path} missing PLUGIN_METADATA"


@pytest.mark.parametrize("module_path", BUILTIN_PLUGIN_MODULES)
def test_plugin_metadata_has_required_fields(module_path: str) -> None:
    """Each PLUGIN_METADATA must have all required fields."""
    module = importlib.import_module(module_path)
    metadata: dict[str, Any] = getattr(module, "PLUGIN_METADATA", {})

    missing = REQUIRED_FIELDS - set(metadata.keys())
    assert not missing, f"{module_path} PLUGIN_METADATA missing fields: {missing}"


@pytest.mark.parametrize("module_path", BUILTIN_PLUGIN_MODULES)
def test_plugin_metadata_compatibility_valid(module_path: str) -> None:
    """compatibility must have min_fapilog_version."""
    module = importlib.import_module(module_path)
    metadata: dict[str, Any] = getattr(module, "PLUGIN_METADATA", {})

    compat = metadata.get("compatibility", {})
    assert "min_fapilog_version" in compat, (
        f"{module_path} compatibility missing min_fapilog_version"
    )


@pytest.mark.parametrize("module_path", BUILTIN_PLUGIN_MODULES)
def test_plugin_metadata_api_version_format(module_path: str) -> None:
    """api_version must be in 'X.Y' format."""
    from fapilog.plugins.versioning import parse_api_version

    module = importlib.import_module(module_path)
    metadata: dict[str, Any] = getattr(module, "PLUGIN_METADATA", {})

    api_version = metadata.get("api_version", "1.0")
    # Should not raise
    major, minor = parse_api_version(api_version)
    assert major == 1, f"{module_path} api_version major must be 1"


@pytest.mark.parametrize("module_path", BUILTIN_PLUGIN_MODULES)
def test_plugin_type_is_valid(module_path: str) -> None:
    """plugin_type must be one of the valid types."""
    module = importlib.import_module(module_path)
    metadata: dict[str, Any] = getattr(module, "PLUGIN_METADATA", {})

    valid_types = {"sink", "processor", "enricher", "redactor", "alerting"}
    plugin_type = metadata.get("plugin_type")
    assert plugin_type in valid_types, (
        f"{module_path} has invalid plugin_type: {plugin_type}"
    )


@pytest.mark.parametrize("module_path", BUILTIN_PLUGIN_MODULES)
def test_plugin_entry_point_format(module_path: str) -> None:
    """entry_point must match 'module.path:ClassName' format."""
    module = importlib.import_module(module_path)
    metadata: dict[str, Any] = getattr(module, "PLUGIN_METADATA", {})

    entry_point = metadata.get("entry_point", "")
    assert ":" in entry_point, f"{module_path} entry_point missing colon separator"

    ep_module, ep_class = entry_point.split(":", 1)
    assert ep_module == module_path, (
        f"{module_path} entry_point module mismatch: {ep_module}"
    )
    assert hasattr(module, ep_class), (
        f"{module_path} entry_point class {ep_class} not found in module"
    )
