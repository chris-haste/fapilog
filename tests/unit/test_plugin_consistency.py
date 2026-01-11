"""
Verify all built-in plugins have consistent configuration.

Story 4.29: Plugin Consistency and Completeness
"""

from __future__ import annotations

import importlib

import pytest

# All built-in plugin modules that should have PLUGIN_METADATA
BUILTIN_PLUGIN_MODULES = [
    # Sinks
    "fapilog.plugins.sinks.stdout_json",
    "fapilog.plugins.sinks.stdout_pretty",
    "fapilog.plugins.sinks.rotating_file",
    "fapilog.plugins.sinks.http_client",
    "fapilog.plugins.sinks.webhook",
    "fapilog.plugins.sinks.mmap_persistence",
    "fapilog.plugins.sinks.contrib.cloudwatch",
    "fapilog.plugins.sinks.contrib.loki",
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

# Expected min_fapilog_version for all built-ins
EXPECTED_MIN_VERSION = "0.3.0"


@pytest.mark.parametrize("module_path", BUILTIN_PLUGIN_MODULES)
def test_plugin_has_metadata(module_path: str) -> None:
    """All built-in plugins should have PLUGIN_METADATA."""
    module = importlib.import_module(module_path)
    assert hasattr(module, "PLUGIN_METADATA"), f"{module_path} missing PLUGIN_METADATA"


@pytest.mark.parametrize("module_path", BUILTIN_PLUGIN_MODULES)
def test_plugin_min_version_is_consistent(module_path: str) -> None:
    """All built-in plugins should use the same min_fapilog_version."""
    module = importlib.import_module(module_path)
    metadata = getattr(module, "PLUGIN_METADATA", {})

    compat = metadata.get("compatibility", {})
    min_version = compat.get("min_fapilog_version")

    assert min_version == EXPECTED_MIN_VERSION, (
        f"{module_path} has min_fapilog_version={min_version!r}, "
        f"expected {EXPECTED_MIN_VERSION!r}"
    )


@pytest.mark.parametrize("module_path", BUILTIN_PLUGIN_MODULES)
def test_plugin_class_has_health_check(module_path: str) -> None:
    """All built-in plugin classes should have health_check method."""
    module = importlib.import_module(module_path)
    metadata = getattr(module, "PLUGIN_METADATA", {})

    # Get the plugin class from entry_point
    entry_point = metadata.get("entry_point", "")
    if ":" in entry_point:
        class_name = entry_point.split(":")[-1]
        plugin_class = getattr(module, class_name, None)
        if plugin_class is not None:
            assert hasattr(plugin_class, "health_check"), (
                f"{module_path}:{class_name} missing health_check method"
            )


@pytest.mark.parametrize("module_path", BUILTIN_PLUGIN_MODULES)
def test_plugin_class_has_name_attribute(module_path: str) -> None:
    """All built-in plugin classes should have name attribute."""
    module = importlib.import_module(module_path)
    metadata = getattr(module, "PLUGIN_METADATA", {})

    entry_point = metadata.get("entry_point", "")
    if ":" in entry_point:
        class_name = entry_point.split(":")[-1]
        plugin_class = getattr(module, class_name, None)
        if plugin_class is not None:
            # Check class-level name attribute
            assert hasattr(plugin_class, "name"), (
                f"{module_path}:{class_name} missing 'name' attribute"
            )
