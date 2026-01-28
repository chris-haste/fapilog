"""
Tests for plugin metadata validation and compatibility checking.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from fapilog.plugins.metadata import (
    PluginCompatibility,
    PluginInfo,
    PluginMetadata,
    create_plugin_metadata,
    validate_fapilog_compatibility,
)


class TestPluginCompatibility:
    """Tests for PluginCompatibility model."""

    def test_valid_min_version(self) -> None:
        """Test valid minimum version."""
        compat = PluginCompatibility(min_fapilog_version="3.0.0")
        assert compat.min_fapilog_version == "3.0.0"
        assert compat.max_fapilog_version is None

    def test_valid_min_and_max_version(self) -> None:
        """Test valid min and max versions."""
        compat = PluginCompatibility(
            min_fapilog_version="3.0.0", max_fapilog_version="4.0.0"
        )
        assert compat.min_fapilog_version == "3.0.0"
        assert compat.max_fapilog_version == "4.0.0"

    def test_invalid_min_version(self) -> None:
        """Test invalid minimum version raises error."""
        with pytest.raises(ValueError, match="Invalid version string"):
            PluginCompatibility(min_fapilog_version="invalid-version")

    def test_invalid_max_version(self) -> None:
        """Test invalid maximum version raises error."""
        with pytest.raises(ValueError, match="Invalid version string"):
            PluginCompatibility(
                min_fapilog_version="3.0.0", max_fapilog_version="not-a-version"
            )

    def test_prerelease_version(self) -> None:
        """Test prerelease versions are valid."""
        compat = PluginCompatibility(min_fapilog_version="3.0.0a1")
        assert compat.min_fapilog_version == "3.0.0a1"


class TestPluginMetadata:
    """Tests for PluginMetadata model."""

    def test_valid_metadata(self) -> None:
        """Test valid plugin metadata."""
        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            plugin_type="sink",
            entry_point="test_plugin.main",
            compatibility=PluginCompatibility(min_fapilog_version="3.0.0"),
        )
        assert metadata.name == "test-plugin"
        assert metadata.version == "1.0.0"
        assert metadata.plugin_type == "sink"

    def test_invalid_plugin_type(self) -> None:
        """Test invalid plugin type raises error."""
        with pytest.raises(ValueError, match="Invalid plugin type"):
            PluginMetadata(
                name="test-plugin",
                version="1.0.0",
                description="Test plugin",
                author="Test Author",
                plugin_type="invalid_type",
                entry_point="test_plugin.main",
                compatibility=PluginCompatibility(min_fapilog_version="3.0.0"),
            )

    def test_filter_plugin_type_is_valid(self) -> None:
        """Test filter plugin type is accepted."""
        metadata = PluginMetadata(
            name="filter-plugin",
            version="1.0.0",
            description="Test filter plugin",
            author="Test Author",
            plugin_type="filter",
            entry_point="test_plugin.main",
            compatibility=PluginCompatibility(min_fapilog_version="3.0.0"),
        )
        assert metadata.plugin_type == "filter"

    def test_all_valid_plugin_types(self) -> None:
        """Test all valid plugin types."""
        for plugin_type in ["sink", "processor", "enricher", "redactor", "filter"]:
            metadata = PluginMetadata(
                name=f"{plugin_type}-plugin",
                version="1.0.0",
                description=f"Test {plugin_type}",
                author="Test",
                plugin_type=plugin_type,
                entry_point="plugin.main",
                compatibility=PluginCompatibility(min_fapilog_version="3.0.0"),
            )
            assert metadata.plugin_type == plugin_type

    def test_alerting_not_valid_plugin_type(self) -> None:
        """Alerting is not a valid plugin type (was designed but never implemented)."""
        with pytest.raises(ValueError, match="Invalid plugin type"):
            PluginMetadata(
                name="test",
                version="1.0.0",
                plugin_type="alerting",
                entry_point="test:Test",
                description="test",
                author="test",
                compatibility=PluginCompatibility(min_fapilog_version="0.3.0"),
            )

    def test_all_builtin_filter_metadata_validates(self) -> None:
        """All built-in filter PLUGIN_METADATA entries should validate."""
        from fapilog.plugins.filters.adaptive_sampling import (
            PLUGIN_METADATA as adaptive_meta,
        )
        from fapilog.plugins.filters.first_occurrence import (
            PLUGIN_METADATA as first_meta,
        )
        from fapilog.plugins.filters.level import PLUGIN_METADATA as level_meta
        from fapilog.plugins.filters.rate_limit import PLUGIN_METADATA as rate_meta
        from fapilog.plugins.filters.sampling import PLUGIN_METADATA as sampling_meta
        from fapilog.plugins.filters.trace_sampling import (
            PLUGIN_METADATA as trace_meta,
        )

        for meta in [
            adaptive_meta,
            first_meta,
            level_meta,
            rate_meta,
            sampling_meta,
            trace_meta,
        ]:
            assert meta["plugin_type"] == "filter"
            PluginMetadata(
                name=meta["name"],
                version=meta["version"],
                description=meta.get("description", ""),
                author=meta.get("author", ""),
                plugin_type=meta["plugin_type"],
                entry_point=meta["entry_point"],
                compatibility=PluginCompatibility(
                    min_fapilog_version=meta.get("compatibility", {}).get(
                        "min_fapilog_version", "0.4.0"
                    )
                ),
                api_version=meta.get("api_version", "1.0"),
            )

    def test_invalid_version(self) -> None:
        """Test invalid version raises error."""
        with pytest.raises(ValueError, match="Invalid version string"):
            PluginMetadata(
                name="test-plugin",
                version="not-a-version",
                description="Test plugin",
                author="Test Author",
                plugin_type="sink",
                entry_point="test_plugin.main",
                compatibility=PluginCompatibility(min_fapilog_version="3.0.0"),
            )

    def test_invalid_api_version(self) -> None:
        """Test invalid API version raises error."""
        with pytest.raises(ValueError):
            PluginMetadata(
                name="test-plugin",
                version="1.0.0",
                description="Test plugin",
                author="Test Author",
                plugin_type="sink",
                entry_point="test_plugin.main",
                compatibility=PluginCompatibility(min_fapilog_version="3.0.0"),
                api_version="invalid",
            )

    def test_valid_api_version(self) -> None:
        """Test valid API version."""
        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            plugin_type="sink",
            entry_point="test_plugin.main",
            compatibility=PluginCompatibility(min_fapilog_version="3.0.0"),
            api_version="1.0",
        )
        assert metadata.api_version == "1.0"

    def test_default_values(self) -> None:
        """Test default values are set correctly."""
        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            plugin_type="sink",
            entry_point="test_plugin.main",
            compatibility=PluginCompatibility(min_fapilog_version="3.0.0"),
        )
        assert metadata.license == "MIT"
        assert metadata.api_version == "1.0"
        assert metadata.dependencies == []
        assert metadata.tags == []
        assert metadata.author_email is None
        assert metadata.homepage is None
        assert metadata.repository is None
        assert metadata.config_schema is None
        assert metadata.default_config is None


class TestPluginInfo:
    """Tests for PluginInfo model."""

    def test_plugin_info_creation(self) -> None:
        """Test PluginInfo creation."""
        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            plugin_type="sink",
            entry_point="test_plugin.main",
            compatibility=PluginCompatibility(min_fapilog_version="3.0.0"),
        )
        info = PluginInfo(metadata=metadata, source="local")
        assert info.loaded is False
        assert info.instance is None
        assert info.load_error is None
        assert info.source == "local"

    def test_plugin_info_with_instance(self) -> None:
        """Test PluginInfo with instance."""
        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            plugin_type="sink",
            entry_point="test_plugin.main",
            compatibility=PluginCompatibility(min_fapilog_version="3.0.0"),
        )

        class MockPlugin:
            pass

        instance = MockPlugin()
        info = PluginInfo(
            metadata=metadata, source="local", loaded=True, instance=instance
        )
        assert info.loaded is True
        assert info.instance is instance

    def test_plugin_info_with_error(self) -> None:
        """Test PluginInfo with load error."""
        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            plugin_type="sink",
            entry_point="test_plugin.main",
            compatibility=PluginCompatibility(min_fapilog_version="3.0.0"),
        )
        info = PluginInfo(
            metadata=metadata,
            source="local",
            loaded=False,
            load_error="Failed to load plugin",
        )
        assert info.loaded is False
        assert info.load_error == "Failed to load plugin"


class TestValidateFapilogCompatibility:
    """Tests for validate_fapilog_compatibility function."""

    @patch("fapilog.plugins.metadata.importlib.metadata.version")
    def test_compatible_version(self, mock_version: Any) -> None:
        """Test compatible version returns True."""
        mock_version.return_value = "0.3.4"

        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            plugin_type="sink",
            entry_point="test_plugin.main",
            compatibility=PluginCompatibility(min_fapilog_version="0.1.0"),
        )
        # Should return True as 0.3.4 >= 0.1.0
        assert validate_fapilog_compatibility(metadata) is True

    @patch("fapilog.plugins.metadata.importlib.metadata.version")
    def test_incompatible_min_version(self, mock_version: Any) -> None:
        """Test incompatible min version returns False."""
        mock_version.return_value = "2.9.0"

        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            plugin_type="sink",
            entry_point="test_plugin.main",
            compatibility=PluginCompatibility(min_fapilog_version="3.0.0"),
        )
        assert validate_fapilog_compatibility(metadata) is False

    @patch("fapilog.plugins.metadata.importlib.metadata.version")
    def test_incompatible_max_version(self, mock_version: Any) -> None:
        """Test incompatible max version returns False."""
        mock_version.return_value = "5.0.0"

        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            plugin_type="sink",
            entry_point="test_plugin.main",
            compatibility=PluginCompatibility(
                min_fapilog_version="3.0.0", max_fapilog_version="4.0.0"
            ),
        )
        assert validate_fapilog_compatibility(metadata) is False

    @patch("fapilog.plugins.metadata.importlib.metadata.version")
    def test_within_version_range(self, mock_version: Any) -> None:
        """Test within version range returns True."""
        mock_version.return_value = "3.5.0"

        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            plugin_type="sink",
            entry_point="test_plugin.main",
            compatibility=PluginCompatibility(
                min_fapilog_version="3.0.0", max_fapilog_version="4.0.0"
            ),
        )
        assert validate_fapilog_compatibility(metadata) is True

    @patch("fapilog.plugins.metadata.importlib.metadata.version")
    def test_editable_install_version(self, mock_version: Any) -> None:
        """Test editable install (0.0.0+local) is universally compatible."""
        mock_version.return_value = "0.0.0+local"

        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            plugin_type="sink",
            entry_point="test_plugin.main",
            compatibility=PluginCompatibility(min_fapilog_version="99.0.0"),
        )
        # Should return True for editable installs
        assert validate_fapilog_compatibility(metadata) is True

    @patch("fapilog.plugins.metadata.importlib.metadata.version")
    @patch("fapilog.__version__", "invalid-version-string")
    def test_version_parsing_error_returns_false_and_warns(
        self, mock_version: Any
    ) -> None:
        """Test version parsing error returns False and emits diagnostic warning."""
        mock_version.side_effect = Exception("Version not found")

        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            plugin_type="sink",
            entry_point="test_plugin.main",
            compatibility=PluginCompatibility(min_fapilog_version="3.0.0"),
        )

        warnings: list[dict[str, Any]] = []

        def capture_warning(payload: dict[str, Any]) -> None:
            warnings.append(payload)

        from fapilog.core import diagnostics

        original_writer = diagnostics._writer
        original_enabled = diagnostics._internal_logging_enabled
        diagnostics.set_writer_for_tests(capture_warning)
        diagnostics.configure_diagnostics(True)
        diagnostics._reset_for_tests()

        try:
            # Should return False on errors (fail-safe behavior)
            result = validate_fapilog_compatibility(metadata)
            assert result is False

            # Should emit a diagnostic warning
            assert len(warnings) == 1
            assert warnings[0]["component"] == "plugins"
            assert "compatibility check failed" in warnings[0]["message"].lower()
            assert "error" in warnings[0]
        finally:
            diagnostics._writer = original_writer
            diagnostics._internal_logging_enabled = original_enabled

    @patch("fapilog.plugins.metadata.importlib.metadata.version")
    def test_fallback_to_local_version(self, mock_version: Any) -> None:
        """Test fallback to __version__ when metadata unavailable."""
        mock_version.side_effect = Exception("Not installed")

        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            plugin_type="sink",
            entry_point="test_plugin.main",
            compatibility=PluginCompatibility(min_fapilog_version="0.0.1"),
        )
        # Uses fallback to local version
        result = validate_fapilog_compatibility(metadata)
        # Should work (permissive on errors or compatible with local version)
        assert result is True


class TestCreatePluginMetadata:
    """Tests for create_plugin_metadata helper function."""

    def test_create_with_required_fields(self) -> None:
        """Test creating metadata with required fields."""
        metadata = create_plugin_metadata(
            name="my-plugin",
            version="1.0.0",
            plugin_type="sink",
            entry_point="my_plugin.main",
        )
        assert metadata.name == "my-plugin"
        assert metadata.version == "1.0.0"
        assert metadata.plugin_type == "sink"
        assert metadata.entry_point == "my_plugin.main"
        assert metadata.description == ""
        assert metadata.author == ""

    def test_create_uses_reasonable_version_default(self) -> None:
        """Default min_fapilog_version is 0.1.0, not 3.0.0.

        Story 10.32 AC4: The project is at version 0.x, so defaulting to 3.0.0
        is incorrect and will cause compatibility check failures for plugin authors.
        """
        metadata = create_plugin_metadata(
            name="test",
            version="1.0.0",
            plugin_type="sink",
            entry_point="test:TestSink",
        )
        assert metadata.compatibility.min_fapilog_version != "3.0.0"
        assert metadata.compatibility.min_fapilog_version == "0.1.0"

    def test_create_with_optional_fields(self) -> None:
        """Test creating metadata with optional fields."""
        metadata = create_plugin_metadata(
            name="my-plugin",
            version="1.0.0",
            plugin_type="enricher",
            entry_point="my_plugin.main",
            description="My awesome plugin",
            author="Test Author",
            tags=["logging", "enricher"],
        )
        assert metadata.description == "My awesome plugin"
        assert metadata.author == "Test Author"
        assert metadata.tags == ["logging", "enricher"]

    def test_create_with_kwargs(self) -> None:
        """Test creating metadata with extra kwargs."""
        metadata = create_plugin_metadata(
            name="my-plugin",
            version="2.0.0",
            plugin_type="processor",
            entry_point="my_plugin.main",
            author_email="test@example.com",
            homepage="https://example.com",
            license="Apache-2.0",
        )
        assert metadata.author_email == "test@example.com"
        assert metadata.homepage == "https://example.com"
        assert metadata.license == "Apache-2.0"
