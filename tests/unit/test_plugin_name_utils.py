"""
TDD tests for Story 4.28: Standardize name Attribute Across All Plugin Protocols.

Tests for plugin name utilities: get_plugin_name, normalize_plugin_name, get_plugin_type.
"""

from __future__ import annotations


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
