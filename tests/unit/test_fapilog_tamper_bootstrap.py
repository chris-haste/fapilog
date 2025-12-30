"""
Tests for fapilog-tamper bootstrap package scaffolding.
"""

from __future__ import annotations

import importlib.metadata
import sys
from importlib.metadata import EntryPoint
from pathlib import Path

import pytest
from pydantic import ValidationError

from fapilog.plugins.integrity import IntegrityPlugin, load_integrity_plugin

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


def _make_entry_points(ep: EntryPoint):
    class _EntryPoints:
        def select(self, *, group: str):
            if group == "fapilog.integrity":
                return [ep]
            return []

    return _EntryPoints()


def test_plugin_discoverable_via_entry_point(monkeypatch: pytest.MonkeyPatch) -> None:
    """Plugin should be discoverable via the integrity entry point group."""
    ep = EntryPoint(
        name="tamper-sealed",
        value="fapilog_tamper:TamperSealedPlugin",
        group="fapilog.integrity",
    )
    monkeypatch.setattr(
        importlib.metadata, "entry_points", lambda: _make_entry_points(ep)
    )

    plugin = load_integrity_plugin("tamper-sealed")

    from fapilog_tamper import TamperSealedPlugin, TamperSealedPluginClass

    assert plugin is TamperSealedPlugin
    assert isinstance(plugin, TamperSealedPluginClass)
    assert isinstance(plugin, IntegrityPlugin)
    assert hasattr(plugin, "get_enricher")
    assert hasattr(plugin, "wrap_sink")


def test_canonicalize_deterministic_and_sorted() -> None:
    """canonicalize should sort keys and exclude integrity field deterministically."""
    from fapilog_tamper.canonical import canonicalize

    event = {"b": 2, "a": 1, "integrity": {"mac": "x"}}
    serialized1 = canonicalize(event)
    serialized2 = canonicalize(dict(event))

    assert serialized1 == serialized2
    assert serialized1 == b'{"a":1,"b":2}'
    # original event should remain unchanged aside from benign integrity exclusion
    assert "integrity" in event


def test_b64url_helpers_round_trip_no_padding() -> None:
    """b64url helpers should round-trip bytes without padding characters."""
    from fapilog_tamper.canonical import b64url_decode, b64url_encode

    data = b"\x00\xffabc123"
    encoded = b64url_encode(data)
    decoded = b64url_decode(encoded)

    assert "=" not in encoded
    assert decoded == data


def test_tamper_config_defaults_and_validation() -> None:
    """TamperConfig should expose sane defaults and strict validation."""
    from fapilog_tamper.config import TamperConfig

    cfg = TamperConfig()
    assert cfg.enabled is False
    assert cfg.algorithm == "HMAC-SHA256"
    assert cfg.key_source == "env"
    assert cfg.key_env_var == "FAPILOG_TAMPER_KEY"
    assert cfg.state_dir == ".fapilog-chainstate"
    assert cfg.fsync_on_write is False
    assert cfg.fsync_on_rotate is True
    assert cfg.rotate_chain is False
    assert cfg.verify_on_close is False
    assert cfg.alert_on_failure is True

    with pytest.raises(ValidationError):
        TamperConfig(algorithm="SHA1")

    with pytest.raises(ValidationError):
        TamperConfig(key_source="database")
