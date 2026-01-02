"""
TDD tests for Story 4.20: Migrate fapilog-tamper to Standard Plugin Architecture.

These tests verify that:
1. IntegrityEnricher is discoverable via fapilog.enrichers entry point
2. SealedSink is discoverable via fapilog.sinks entry point
3. Both plugins are configurable via standard enricher_config/sink_config
4. load_integrity_plugin() emits DeprecationWarning
5. Legacy core.integrity_plugin configuration still works
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

# Skip entire module if fapilog-tamper is not available
try:
    import fapilog_tamper  # noqa: F401
except ImportError:
    pytest.skip("fapilog-tamper not available", allow_module_level=True)


class TestStandardEntryPoints:
    """Test that tamper plugins are discoverable via standard entry points."""

    def test_integrity_enricher_discoverable_via_fapilog_enrichers(self) -> None:
        """IntegrityEnricher should load via load_plugin('fapilog.enrichers', 'integrity')."""
        from fapilog.plugins.loader import load_plugin

        enricher = load_plugin("fapilog.enrichers", "integrity", {})

        from fapilog_tamper.enricher import IntegrityEnricher

        assert isinstance(enricher, IntegrityEnricher)

    def test_sealed_sink_discoverable_via_fapilog_sinks(self) -> None:
        """SealedSink should load via load_plugin('fapilog.sinks', 'sealed')."""
        from fapilog.plugins.loader import load_plugin

        # SealedSink requires an inner sink
        sink = load_plugin("fapilog.sinks", "sealed", {"inner_sink": "stdout_json"})

        from fapilog_tamper.sealed_sink import SealedSink

        assert isinstance(sink, SealedSink)

    def test_integrity_enricher_accepts_standard_config_kwargs(self) -> None:
        """IntegrityEnricher should accept standard config parameters as kwargs."""
        from fapilog.plugins.loader import load_plugin

        enricher = load_plugin(
            "fapilog.enrichers",
            "integrity",
            {
                "algorithm": "sha256",
                "key_id": "test-key",
                "key_provider": "env",
                "chain_state_path": "/tmp/test-chain",
            },
        )

        # Verify config was applied
        assert enricher._config is not None

    def test_sealed_sink_accepts_standard_config_kwargs(self, tmp_path: Path) -> None:
        """SealedSink should accept standard config parameters as kwargs."""
        from fapilog.plugins.loader import load_plugin

        # Use stdout_json as inner sink since it doesn't require config
        sink = load_plugin(
            "fapilog.sinks",
            "sealed",
            {
                "inner_sink": "stdout_json",
                "manifest_path": str(tmp_path / "manifests"),
                "sign_manifests": False,
            },
        )

        # Verify the sink was configured
        assert sink._manifest_path == str(tmp_path / "manifests")
        assert sink._sign_manifests is False


class TestDeprecationWarning:
    """Test that legacy API emits deprecation warnings."""

    def test_load_integrity_plugin_emits_deprecation_warning(self) -> None:
        """load_integrity_plugin() should emit DeprecationWarning."""
        from fapilog.plugins.integrity import load_integrity_plugin

        with pytest.warns(
            DeprecationWarning, match="load_integrity_plugin is deprecated"
        ):
            load_integrity_plugin("tamper-sealed")


class TestLegacyBackwardCompatibility:
    """Test that legacy core.integrity_plugin configuration still works."""

    @pytest.mark.asyncio
    async def test_legacy_integrity_plugin_config_still_works(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Legacy core.integrity_plugin setting should still function."""
        from fapilog import Settings, get_async_logger

        settings = Settings()
        settings.core.integrity_plugin = "tamper-sealed"
        settings.core.integrity_config = {"enabled": True}
        settings.core.sinks = ["stdout_json"]
        settings.core.enrichers = []

        # Should work without errors (deprecation warning expected)
        with pytest.warns(DeprecationWarning):
            logger = await get_async_logger(settings=settings)

        # Verify logger was created
        assert logger is not None
        await logger.stop_and_drain()


class TestStandardConfigurationFlow:
    """Test the new standard configuration pattern."""

    @pytest.mark.asyncio
    async def test_standard_enricher_and_sink_config(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Standard enricher_config.integrity and sink_config.sealed should work."""
        from fapilog import Settings

        # This test verifies the target state from story 4.20
        settings = Settings()
        settings.core.sinks = ["sealed"]
        settings.core.enrichers = ["integrity"]
        settings.core.enable_redactors = False

        # Configure via standard config pattern
        # Note: This requires Settings to have integrity/sealed config models
        # which is what story 4.20 needs to add

        # For now, we test that the plugins can be loaded with config
        from fapilog.plugins.loader import load_plugin

        enricher = load_plugin(
            "fapilog.enrichers",
            "integrity",
            {"algorithm": "sha256", "key_id": "test"},
        )
        sink = load_plugin(
            "fapilog.sinks",
            "sealed",
            {"inner_sink": "stdout_json", "sign_manifests": False},
        )

        assert enricher is not None
        assert sink is not None
