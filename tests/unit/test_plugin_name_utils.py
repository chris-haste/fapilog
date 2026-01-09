"""
TDD tests for Story 4.28: Standardize name Attribute Across All Plugin Protocols.

Tests for plugin name utilities: get_plugin_name, normalize_plugin_name, get_plugin_type.
"""

from __future__ import annotations

import sys
import types

from pydantic import BaseModel


class PluginWithName:
    """Test plugin with explicit name attribute."""

    name = "test-plugin"

    async def write(self, entry: dict) -> None:
        pass


class PluginWithoutName:
    """Test plugin without name attribute."""

    async def write(self, entry: dict) -> None:
        pass


class PluginWithEmptyName:
    """Test plugin with empty name."""

    name = ""

    async def write(self, entry: dict) -> None:
        pass


class PluginWithWhitespaceName:
    """Test plugin with whitespace-only name."""

    name = "   "

    async def write(self, entry: dict) -> None:
        pass


class TestGetPluginName:
    """Tests for get_plugin_name utility."""

    def test_get_plugin_name_from_attribute(self) -> None:
        """Plugin with name attribute returns that name."""
        from fapilog.plugins.utils import get_plugin_name

        plugin = PluginWithName()
        assert get_plugin_name(plugin) == "test-plugin"

    def test_get_plugin_name_fallback_to_class(self) -> None:
        """Plugin without name attribute falls back to class name."""
        from fapilog.plugins.utils import get_plugin_name

        plugin = PluginWithoutName()
        assert get_plugin_name(plugin) == "PluginWithoutName"

    def test_get_plugin_name_empty_name_uses_class(self) -> None:
        """Empty name attribute falls back to class name."""
        from fapilog.plugins.utils import get_plugin_name

        plugin = PluginWithEmptyName()
        assert get_plugin_name(plugin) == "PluginWithEmptyName"

    def test_get_plugin_name_whitespace_name_uses_class(self) -> None:
        """Whitespace-only name attribute falls back to class name."""
        from fapilog.plugins.utils import get_plugin_name

        plugin = PluginWithWhitespaceName()
        assert get_plugin_name(plugin) == "PluginWithWhitespaceName"

    def test_get_plugin_name_on_class_not_instance(self) -> None:
        """get_plugin_name works on class, not just instance."""
        from fapilog.plugins.utils import get_plugin_name

        assert get_plugin_name(PluginWithName) == "test-plugin"

    def test_get_plugin_name_strips_whitespace(self) -> None:
        """Plugin name is stripped of leading/trailing whitespace."""
        from fapilog.plugins.utils import get_plugin_name

        class PaddedName:
            name = "  padded  "

        assert get_plugin_name(PaddedName()) == "padded"

    def test_get_plugin_name_from_module_metadata(self) -> None:
        """PLUGIN_METADATA name should be used when present."""
        from fapilog.plugins.utils import get_plugin_name

        module_name = "tests.fake_plugin_module"
        module = types.ModuleType(module_name)
        module.PLUGIN_METADATA = {"name": "from-metadata"}

        class Plugin:
            pass

        Plugin.__module__ = module_name
        module.Plugin = Plugin
        sys.modules[module_name] = module
        try:
            assert get_plugin_name(Plugin()) == "from-metadata"
        finally:
            sys.modules.pop(module_name, None)

    def test_get_plugin_name_falls_back_when_metadata_missing_name(self) -> None:
        """Metadata without name should fall back to class name."""
        from fapilog.plugins.utils import get_plugin_name

        module_name = "tests.fake_plugin_module_no_name"
        module = types.ModuleType(module_name)
        module.PLUGIN_METADATA = {"version": "1.0.0"}

        class Plugin:
            pass

        Plugin.__module__ = module_name
        module.Plugin = Plugin
        sys.modules[module_name] = module
        try:
            assert get_plugin_name(Plugin()) == "Plugin"
        finally:
            sys.modules.pop(module_name, None)

    def test_get_plugin_name_falls_back_on_import_error(self) -> None:
        """Import errors in metadata lookup fall back to class name."""
        from fapilog.plugins.utils import get_plugin_name

        class Ghost:
            pass

        Ghost.__module__ = "missing.module.name"
        assert get_plugin_name(Ghost()) == "Ghost"

    def test_get_plugin_name_falls_back_when_module_name_missing(self) -> None:
        """Missing module name should fall back to class name."""
        from fapilog.plugins.utils import get_plugin_name

        class Nameless:
            pass

        Nameless.__module__ = ""
        assert get_plugin_name(Nameless()) == "Nameless"


class TestNormalizePluginName:
    """Tests for normalize_plugin_name utility."""

    def test_normalize_hyphen_to_underscore(self) -> None:
        """Hyphens are converted to underscores."""
        from fapilog.plugins.utils import normalize_plugin_name

        assert normalize_plugin_name("field-mask") == "field_mask"

    def test_normalize_lowercase(self) -> None:
        """Names are lowercased."""
        from fapilog.plugins.utils import normalize_plugin_name

        assert normalize_plugin_name("Field-Mask") == "field_mask"

    def test_normalize_already_normalized(self) -> None:
        """Already normalized names pass through."""
        from fapilog.plugins.utils import normalize_plugin_name

        assert normalize_plugin_name("runtime_info") == "runtime_info"

    def test_normalize_complex_name(self) -> None:
        """Complex names with multiple hyphens are normalized."""
        from fapilog.plugins.utils import normalize_plugin_name

        assert normalize_plugin_name("URL-Credentials-Mask") == "url_credentials_mask"


class TestGetPluginType:
    """Tests for get_plugin_type utility."""

    def test_get_plugin_type_sink(self) -> None:
        """Plugin with write method is a sink."""
        from fapilog.plugins.utils import get_plugin_type

        class Sink:
            async def write(self, entry: dict) -> None:
                pass

        assert get_plugin_type(Sink()) == "sink"

    def test_get_plugin_type_enricher(self) -> None:
        """Plugin with enrich method is an enricher."""
        from fapilog.plugins.utils import get_plugin_type

        class Enricher:
            async def enrich(self, event: dict) -> dict:
                return event

        assert get_plugin_type(Enricher()) == "enricher"

    def test_get_plugin_type_redactor(self) -> None:
        """Plugin with redact method is a redactor."""
        from fapilog.plugins.utils import get_plugin_type

        class Redactor:
            async def redact(self, event: dict) -> dict:
                return event

        assert get_plugin_type(Redactor()) == "redactor"

    def test_get_plugin_type_processor(self) -> None:
        """Plugin with process method is a processor."""
        from fapilog.plugins.utils import get_plugin_type

        class Processor:
            async def process(self, view: memoryview) -> memoryview:
                return view

        assert get_plugin_type(Processor()) == "processor"

    def test_get_plugin_type_filter(self) -> None:
        """Plugin with filter method is a filter."""
        from fapilog.plugins.utils import get_plugin_type

        class Filter:
            async def filter(self, event: dict) -> bool:
                return True

        assert get_plugin_type(Filter()) == "filter"

    def test_get_plugin_type_unknown(self) -> None:
        """Plugin without recognized method is unknown."""
        from fapilog.plugins.utils import get_plugin_type

        class Unknown:
            pass

        assert get_plugin_type(Unknown()) == "unknown"

    def test_get_plugin_type_works_on_class(self) -> None:
        """get_plugin_type works on class, not just instance."""
        from fapilog.plugins.utils import get_plugin_type

        class Sink:
            async def write(self, entry: dict) -> None:
                pass

        assert get_plugin_type(Sink) == "sink"


class DemoConfig(BaseModel):
    value: int = 1


class TestParsePluginConfigExtras:
    def test_nested_config_instance_is_returned(self) -> None:
        from fapilog.plugins.utils import parse_plugin_config

        cfg = DemoConfig(value=2)
        result = parse_plugin_config(DemoConfig, {"config": cfg})
        assert result is cfg

    def test_kwargs_config_instance_is_returned(self) -> None:
        from fapilog.plugins.utils import parse_plugin_config

        cfg = DemoConfig(value=3)
        result = parse_plugin_config(DemoConfig, None, config=cfg)
        assert result is cfg

    def test_kwargs_config_non_mapping_is_ignored(self) -> None:
        from fapilog.plugins.utils import parse_plugin_config

        result = parse_plugin_config(DemoConfig, None, config="ignored", value=4)
        assert result.value == 4
