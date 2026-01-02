"""
TDD tests for Story 4.20a: Remove Deprecated IntegrityPlugin Protocol.

These tests verify that deprecated code has been removed:
1. IntegrityPlugin protocol is no longer exported
2. load_integrity_plugin() function is removed
3. core.integrity_plugin and core.integrity_config settings are removed
4. _TamperSealedPlugin class is removed from fapilog-tamper
5. fapilog.integrity entry point group no longer works

These tests should FAIL before implementation and PASS after.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add fapilog-tamper to path before importing
_tamper_src = (
    Path(__file__).resolve().parents[2] / "packages" / "fapilog-tamper" / "src"
)
if _tamper_src.exists():
    sys.path.insert(0, str(_tamper_src))


class TestIntegrityPluginRemoval:
    """Verify IntegrityPlugin protocol is removed from fapilog.plugins."""

    def test_integrity_plugin_not_exported_from_plugins(self) -> None:
        """IntegrityPlugin should NOT be importable from fapilog.plugins."""
        from fapilog import plugins

        assert not hasattr(plugins, "IntegrityPlugin"), (
            "IntegrityPlugin should be removed from fapilog.plugins"
        )

    def test_load_integrity_plugin_not_exported(self) -> None:
        """load_integrity_plugin should NOT be importable from fapilog.plugins."""
        from fapilog import plugins

        assert not hasattr(plugins, "load_integrity_plugin"), (
            "load_integrity_plugin should be removed from fapilog.plugins"
        )

    def test_integrity_module_deleted(self) -> None:
        """src/fapilog/plugins/integrity.py should not exist."""
        integrity_path = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "fapilog"
            / "plugins"
            / "integrity.py"
        )
        assert not integrity_path.exists(), (
            f"integrity.py should be deleted: {integrity_path}"
        )


class TestSettingsRemoval:
    """Verify deprecated settings fields are removed."""

    def test_core_settings_no_integrity_plugin_field(self) -> None:
        """CoreSettings should NOT have integrity_plugin field."""
        from fapilog import Settings

        settings = Settings()
        assert not hasattr(settings.core, "integrity_plugin"), (
            "core.integrity_plugin should be removed"
        )

    def test_core_settings_no_integrity_config_field(self) -> None:
        """CoreSettings should NOT have integrity_config field."""
        from fapilog import Settings

        settings = Settings()
        assert not hasattr(settings.core, "integrity_config"), (
            "core.integrity_config should be removed"
        )


class TestTamperPluginRemoval:
    """Verify legacy TamperSealedPlugin is removed from fapilog-tamper."""

    def test_tamper_sealed_plugin_not_exported(self) -> None:
        """TamperSealedPlugin should NOT be importable from fapilog_tamper."""
        try:
            import fapilog_tamper
        except ImportError:
            pytest.skip("fapilog-tamper not available")

        assert not hasattr(fapilog_tamper, "TamperSealedPlugin"), (
            "TamperSealedPlugin should be removed from fapilog_tamper"
        )

    def test_plugin_module_deleted(self) -> None:
        """packages/fapilog-tamper/src/fapilog_tamper/plugin.py should not exist."""
        plugin_path = (
            Path(__file__).resolve().parents[2]
            / "packages"
            / "fapilog-tamper"
            / "src"
            / "fapilog_tamper"
            / "plugin.py"
        )
        assert not plugin_path.exists(), f"plugin.py should be deleted: {plugin_path}"


class TestLegacyEntryPointRemoval:
    """Verify fapilog.integrity entry point group is removed."""

    def test_integrity_entry_point_not_available(self) -> None:
        """fapilog.integrity entry point group should yield no plugins."""
        import importlib.metadata

        eps = importlib.metadata.entry_points()

        # Try both old and new API
        if hasattr(eps, "select"):
            integrity_eps = list(eps.select(group="fapilog.integrity"))
        elif hasattr(eps, "get"):
            integrity_eps = eps.get("fapilog.integrity", [])
        else:
            integrity_eps = []

        assert len(integrity_eps) == 0, (
            f"fapilog.integrity entry points should be removed, found: {integrity_eps}"
        )


class TestStandardPathStillWorks:
    """Verify standard plugin loading still works after removal."""

    def test_integrity_enricher_still_loads_via_standard_path(self) -> None:
        """IntegrityEnricher should still load via fapilog.enrichers."""
        from fapilog.plugins.loader import load_plugin

        enricher = load_plugin("fapilog.enrichers", "integrity", {})
        assert enricher is not None

    def test_sealed_sink_still_loads_via_standard_path(self) -> None:
        """SealedSink should still load via fapilog.sinks."""
        from fapilog.plugins.loader import load_plugin

        sink = load_plugin("fapilog.sinks", "sealed", {"inner_sink": "stdout_json"})
        assert sink is not None
