"""
TDD tests for Story 4.28: Verify all built-in plugins have name attributes.

Each built-in plugin should have a consistent `name` class attribute.
"""

from __future__ import annotations

import pytest

# Expected name for each built-in plugin class
BUILTIN_PLUGINS = [
    ("fapilog.plugins.sinks.stdout_json", "StdoutJsonSink", "stdout_json"),
    ("fapilog.plugins.sinks.stdout_pretty", "StdoutPrettySink", "stdout_pretty"),
    ("fapilog.plugins.sinks.rotating_file", "RotatingFileSink", "rotating_file"),
    ("fapilog.plugins.sinks.http_client", "HttpSink", "http"),
    ("fapilog.plugins.sinks.webhook", "WebhookSink", "webhook"),
    (
        "fapilog.plugins.sinks.mmap_persistence",
        "MemoryMappedPersistence",
        "mmap_persistence",
    ),
    (
        "fapilog.plugins.sinks.contrib.cloudwatch",
        "CloudWatchSink",
        "cloudwatch",
    ),
    (
        "fapilog.plugins.sinks.contrib.loki",
        "LokiSink",
        "loki",
    ),
    (
        "fapilog.plugins.sinks.contrib.postgres",
        "PostgresSink",
        "postgres",
    ),
    ("fapilog.plugins.sinks.routing", "RoutingSink", "routing"),
    ("fapilog.plugins.enrichers.runtime_info", "RuntimeInfoEnricher", "runtime_info"),
    ("fapilog.plugins.enrichers.context_vars", "ContextVarsEnricher", "context_vars"),
    ("fapilog.plugins.enrichers.kubernetes", "KubernetesEnricher", "kubernetes"),
    ("fapilog.plugins.redactors.field_mask", "FieldMaskRedactor", "field_mask"),
    ("fapilog.plugins.redactors.regex_mask", "RegexMaskRedactor", "regex_mask"),
    (
        "fapilog.plugins.redactors.url_credentials",
        "UrlCredentialsRedactor",
        "url_credentials",
    ),
    ("fapilog.plugins.processors.zero_copy", "ZeroCopyProcessor", "zero_copy"),
    ("fapilog.plugins.processors.size_guard", "SizeGuardProcessor", "size_guard"),
]


@pytest.mark.parametrize("module_path,class_name,expected_name", BUILTIN_PLUGINS)
def test_builtin_plugin_has_name_attribute(
    module_path: str, class_name: str, expected_name: str
) -> None:
    """Each built-in plugin class must have a name attribute."""
    import importlib

    module = importlib.import_module(module_path)
    plugin_class = getattr(module, class_name)

    assert hasattr(plugin_class, "name"), f"{class_name} missing name attribute"


@pytest.mark.parametrize("module_path,class_name,expected_name", BUILTIN_PLUGINS)
def test_builtin_plugin_name_is_correct(
    module_path: str, class_name: str, expected_name: str
) -> None:
    """Each built-in plugin's name attribute matches expected value."""
    import importlib

    module = importlib.import_module(module_path)
    plugin_class = getattr(module, class_name)

    assert plugin_class.name == expected_name, (
        f"{class_name}.name is '{plugin_class.name}', expected '{expected_name}'"
    )


@pytest.mark.parametrize("module_path,class_name,expected_name", BUILTIN_PLUGINS)
def test_builtin_plugin_name_is_nonempty_string(
    module_path: str, class_name: str, expected_name: str
) -> None:
    """Each built-in plugin's name is a non-empty string."""
    import importlib

    module = importlib.import_module(module_path)
    plugin_class = getattr(module, class_name)

    assert isinstance(plugin_class.name, str), f"{class_name}.name is not a string"
    assert plugin_class.name.strip(), f"{class_name}.name is empty or whitespace"
