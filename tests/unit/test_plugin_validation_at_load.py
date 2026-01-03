from __future__ import annotations

import pytest

from fapilog import _apply_plugin_settings
from fapilog.core.settings import Settings
from fapilog.plugins import loader
from fapilog.testing import validators


@pytest.fixture
def clean_registries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate plugin registries and validation mode per test."""
    monkeypatch.setattr(loader, "BUILTIN_SINKS", {}, raising=False)
    monkeypatch.setattr(loader, "BUILTIN_ALIASES", {"fapilog.sinks": {}}, raising=False)
    monkeypatch.setattr(
        loader, "_validation_mode", loader.ValidationMode.DISABLED, raising=False
    )


def _register_invalid_sink() -> type:
    class InvalidSink:
        name = "invalid"

        async def start(self) -> None:  # pragma: no cover - used via loader
            return None

        async def stop(self) -> None:  # pragma: no cover - used via loader
            return None

    loader.register_builtin("fapilog.sinks", "invalid", InvalidSink)
    return InvalidSink


def test_validation_strict_rejects_invalid(clean_registries: None) -> None:
    _register_invalid_sink()

    with pytest.raises(loader.PluginLoadError, match="failed validation"):
        loader.load_plugin(
            "fapilog.sinks",
            "invalid",
            validation_mode=loader.ValidationMode.STRICT,
        )


def test_validation_warn_logs_but_loads(
    clean_registries: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[tuple[str, str, dict[str, object]]] = []

    def _capture_warn(component: str, message: str, **fields: object) -> None:
        captured.append((component, message, fields))

    monkeypatch.setattr(loader.diagnostics, "warn", _capture_warn)
    InvalidSink = _register_invalid_sink()

    plugin = loader.load_plugin(
        "fapilog.sinks",
        "invalid",
        validation_mode=loader.ValidationMode.WARN,
    )

    assert isinstance(plugin, InvalidSink)
    assert captured, "expected diagnostics warning in WARN mode"
    component, message, fields = captured[0]
    assert component == "plugins"
    assert "validation failed" in message
    assert fields.get("plugin") == "invalid"


def test_validation_disabled_skips_checks(
    clean_registries: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _failing_validator(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("validation should be skipped")

    monkeypatch.setattr(validators, "validate_sink", _failing_validator)
    InvalidSink = _register_invalid_sink()

    plugin = loader.load_plugin(
        "fapilog.sinks",
        "invalid",
        validation_mode=loader.ValidationMode.DISABLED,
    )

    assert isinstance(plugin, InvalidSink)


def test_settings_apply_validation_mode_default(
    clean_registries: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAPILOG_PLUGINS__VALIDATION_MODE", "strict")
    settings = Settings()
    _apply_plugin_settings(settings)
    _register_invalid_sink()

    with pytest.raises(loader.PluginLoadError):
        loader.load_plugin("fapilog.sinks", "invalid")
