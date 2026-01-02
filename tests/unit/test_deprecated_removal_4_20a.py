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
from types import SimpleNamespace
from typing import Any

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


def _fake_entry_points(*eps: tuple[str, str, Any]) -> Any:
    """Create a fake entry_points() return value."""
    ep_list = [SimpleNamespace(name=n, group=g, load=lambda t=t: t) for n, g, t in eps]

    class _EPs:
        def select(self, *, group: str) -> list[Any]:
            return [ep for ep in ep_list if ep.group == group]

        def get(self, group: str, default: Any = None) -> list[Any]:
            return [ep for ep in ep_list if ep.group == group] or default or []

    return _EPs()


class TestStandardPathStillWorks:
    """Verify standard plugin loading still works after removal (with mocked entry points)."""

    def test_integrity_enricher_still_loads_via_standard_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """IntegrityEnricher should still load via fapilog.enrichers."""
        try:
            from fapilog_tamper.enricher import IntegrityEnricher
        except ImportError:
            pytest.skip("fapilog-tamper not available")

        from fapilog.plugins import loader

        fake_eps = _fake_entry_points(
            ("integrity", "fapilog.enrichers", IntegrityEnricher),
        )
        monkeypatch.setattr(loader.importlib.metadata, "entry_points", lambda: fake_eps)
        monkeypatch.setattr(loader, "BUILTIN_ENRICHERS", {})

        enricher = loader.load_plugin("fapilog.enrichers", "integrity", {})
        assert enricher is not None
        assert isinstance(enricher, IntegrityEnricher)

    def test_sealed_sink_still_loads_via_standard_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SealedSink should still load via fapilog.sinks."""
        try:
            from fapilog_tamper.sealed_sink import SealedSink
        except ImportError:
            pytest.skip("fapilog-tamper not available")

        from fapilog.plugins import loader

        fake_eps = _fake_entry_points(
            ("sealed", "fapilog.sinks", SealedSink),
        )
        monkeypatch.setattr(loader.importlib.metadata, "entry_points", lambda: fake_eps)
        # Keep stdout_json in builtins so SealedSink can resolve its inner sink
        original_sinks = loader.BUILTIN_SINKS.copy()
        monkeypatch.setattr(
            loader, "BUILTIN_SINKS", {"stdout_json": original_sinks.get("stdout_json")}
        )

        sink = loader.load_plugin(
            "fapilog.sinks", "sealed", {"inner_sink": "stdout_json"}
        )
        assert sink is not None
        assert isinstance(sink, SealedSink)
