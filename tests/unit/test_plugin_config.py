from typing import Any

from fapilog.core.plugin_config import (
    ValidationIssue,
    check_dependencies,
    validate_plugin_configuration,
)
from fapilog.plugins.metadata import (
    PluginCompatibility,
    PluginInfo,
    PluginMetadata,
)


def _make_plugin(
    *,
    name: str = "demo",
    config_schema: Any = None,
    default_config: Any = None,
    dependencies: Any = None,
) -> PluginInfo:
    meta = PluginMetadata(
        name=name,
        version="1.0.0",
        plugin_type="sink",
        entry_point="demo:Plugin",
        description="",
        author="",
        compatibility=PluginCompatibility(min_fapilog_version="0.0.0"),
        config_schema=config_schema or None,
        default_config=default_config or None,
        dependencies=dependencies or [],
    )
    return PluginInfo(metadata=meta, loaded=False, source="entry_point")


def test_quality_gates_warn_on_missing_metadata() -> None:
    plugin = _make_plugin()
    result = validate_plugin_configuration(plugin)
    # Should be ok (only warnings)
    assert result.ok is True
    assert any(isinstance(i, ValidationIssue) for i in result.issues)


def test_schema_required_keys_fail() -> None:
    schema = {"required": ["url"], "properties": {"url": {"type": "string"}}}
    plugin = _make_plugin(config_schema=schema, default_config={})
    result = validate_plugin_configuration(plugin)
    assert result.ok is False
    assert any(i.field == "url" for i in result.issues)


def test_schema_type_validation() -> None:
    schema = {
        "required": ["port"],
        "properties": {"port": {"type": "integer"}},
    }
    plugin = _make_plugin(config_schema=schema, default_config={"port": "abc"})
    result = validate_plugin_configuration(plugin)
    assert result.ok is False
    assert any(
        i.field == "port" and "expected type" in i.message for i in result.issues
    )


def test_dependency_check_handles_missing_and_conflicts() -> None:
    meta = _make_plugin(dependencies=["nonexistentpkg>=1.0.0"]).metadata
    missing, conflicts = check_dependencies(meta)
    assert any(r.startswith("nonexistentpkg") for r in missing)
