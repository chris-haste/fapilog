"""
TDD tests for Story 4.20: Migrate fapilog-tamper to Standard Plugin Architecture.

These tests verify that:
1. IntegrityEnricher is discoverable via fapilog.enrichers entry point
2. SealedSink is discoverable via fapilog.sinks entry point
3. Both plugins are configurable via standard enricher_config/sink_config
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

# Skip entire module if fapilog-tamper is not available
try:
    from fapilog_tamper.enricher import IntegrityEnricher
    from fapilog_tamper.sealed_sink import SealedSink
except ImportError:
    pytest.skip("fapilog-tamper not available", allow_module_level=True)


def _fake_entry_point(name: str, target: Any) -> Any:
    """Create a fake entry point for testing."""
    return SimpleNamespace(name=name, load=lambda: target)


def _fake_entry_points(*eps: tuple[str, str, Any]) -> Any:
    """Create a fake entry_points() return value."""
    ep_list = [SimpleNamespace(name=n, group=g, load=lambda t=t: t) for n, g, t in eps]

    class _EPs:
        def select(self, *, group: str) -> list[Any]:
            return [ep for ep in ep_list if ep.group == group]

        def get(self, group: str, default: Any = None) -> list[Any]:
            return [ep for ep in ep_list if ep.group == group] or default or []

    return _EPs()


class TestStandardEntryPoints:
    """Test that tamper plugins are discoverable via standard entry points."""

    def test_integrity_enricher_discoverable_via_fapilog_enrichers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """IntegrityEnricher should load via load_plugin('fapilog.enrichers', 'integrity')."""
        from fapilog.plugins import loader

        # Mock entry points to simulate installed package
        fake_eps = _fake_entry_points(
            ("integrity", "fapilog.enrichers", IntegrityEnricher),
        )
        monkeypatch.setattr(loader.importlib.metadata, "entry_points", lambda: fake_eps)
        monkeypatch.setattr(loader, "BUILTIN_ENRICHERS", {})

        enricher = loader.load_plugin("fapilog.enrichers", "integrity", {})
        assert isinstance(enricher, IntegrityEnricher)

    def test_sealed_sink_discoverable_via_fapilog_sinks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SealedSink should load via load_plugin('fapilog.sinks', 'sealed')."""
        from fapilog.plugins import loader

        fake_eps = _fake_entry_points(
            ("sealed", "fapilog.sinks", SealedSink),
        )
        monkeypatch.setattr(loader.importlib.metadata, "entry_points", lambda: fake_eps)
        monkeypatch.setattr(
            loader,
            "BUILTIN_SINKS",
            {"stdout_json": loader.BUILTIN_SINKS.get("stdout_json")},
        )

        sink = loader.load_plugin(
            "fapilog.sinks", "sealed", {"inner_sink": "stdout_json"}
        )
        assert isinstance(sink, SealedSink)

    def test_integrity_enricher_accepts_standard_config_kwargs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """IntegrityEnricher should accept standard config parameters as kwargs."""
        from fapilog.plugins import loader

        fake_eps = _fake_entry_points(
            ("integrity", "fapilog.enrichers", IntegrityEnricher),
        )
        monkeypatch.setattr(loader.importlib.metadata, "entry_points", lambda: fake_eps)
        monkeypatch.setattr(loader, "BUILTIN_ENRICHERS", {})

        enricher = loader.load_plugin(
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

    def test_sealed_sink_accepts_standard_config_kwargs(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """SealedSink should accept standard config parameters as kwargs."""
        from fapilog.plugins import loader

        fake_eps = _fake_entry_points(
            ("sealed", "fapilog.sinks", SealedSink),
        )
        monkeypatch.setattr(loader.importlib.metadata, "entry_points", lambda: fake_eps)
        monkeypatch.setattr(
            loader,
            "BUILTIN_SINKS",
            {"stdout_json": loader.BUILTIN_SINKS.get("stdout_json")},
        )

        sink = loader.load_plugin(
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


class TestStandardConfigurationFlow:
    """Test the new standard configuration pattern."""

    @pytest.mark.asyncio
    async def test_standard_enricher_and_sink_config(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Standard enricher_config.integrity and sink_config.sealed should work."""
        from fapilog import Settings
        from fapilog.plugins import loader

        fake_eps = _fake_entry_points(
            ("integrity", "fapilog.enrichers", IntegrityEnricher),
            ("sealed", "fapilog.sinks", SealedSink),
        )
        monkeypatch.setattr(loader.importlib.metadata, "entry_points", lambda: fake_eps)
        monkeypatch.setattr(loader, "BUILTIN_ENRICHERS", {})
        monkeypatch.setattr(
            loader,
            "BUILTIN_SINKS",
            {"stdout_json": loader.BUILTIN_SINKS.get("stdout_json")},
        )

        # This test verifies the target state from story 4.20
        settings = Settings()
        settings.core.sinks = ["sealed"]
        settings.core.enrichers = ["integrity"]
        settings.core.enable_redactors = False

        enricher = loader.load_plugin(
            "fapilog.enrichers",
            "integrity",
            {"algorithm": "sha256", "key_id": "test"},
        )
        sink = loader.load_plugin(
            "fapilog.sinks",
            "sealed",
            {"inner_sink": "stdout_json", "sign_manifests": False},
        )

        assert enricher is not None
        assert sink is not None
