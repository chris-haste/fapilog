"""Tests for plugin security settings (Story 3.5).

AC1: Built-ins only by default - external plugins blocked unless explicitly enabled.
AC2: Explicit opt-in for external plugins via allow_external or allowlist.
AC3: Warning emitted when loading external plugins.
"""

from __future__ import annotations

import types
from typing import Any

import pytest

from fapilog.core.settings import Settings
from fapilog.plugins import loader


class _DummyPlugin:
    """Test plugin class."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


def _fake_entry_point(name: str, target: Any) -> Any:
    """Create a fake entry point for testing."""
    ep = types.SimpleNamespace()
    ep.name = name
    ep.load = lambda: target
    return ep


class TestAllowExternalSetting:
    """AC1: allow_external defaults to False, blocking external plugins."""

    def test_allow_external_defaults_to_false(self) -> None:
        """By default, external plugins are not allowed."""
        settings = Settings()
        assert settings.plugins.allow_external is False

    def test_allow_external_can_be_enabled(self) -> None:
        """Users can explicitly enable external plugins."""
        settings = Settings(plugins={"allow_external": True})
        assert settings.plugins.allow_external is True


class TestBuiltinPluginsAlwaysAllowed:
    """AC1: Built-in plugins load regardless of allow_external setting."""

    def test_builtin_plugin_loads_with_default_settings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Built-in plugins work with default settings (allow_external=False)."""
        monkeypatch.setattr(loader, "BUILTIN_SINKS", {"console": _DummyPlugin})
        monkeypatch.setattr(loader, "BUILTIN_ALIASES", {"fapilog.sinks": {}})

        # Should load successfully even with allow_external=False
        inst = loader.load_plugin(
            "fapilog.sinks", "console", {}, allow_external=False, allowlist=[]
        )
        assert isinstance(inst, _DummyPlugin)


class TestExternalPluginBlocking:
    """AC1/AC2: External (entry point) plugins require explicit opt-in."""

    def test_entry_point_blocked_by_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Entry point plugins are blocked when allow_external=False."""
        monkeypatch.setattr(loader, "BUILTIN_SINKS", {})
        monkeypatch.setattr(loader, "BUILTIN_ALIASES", {})

        fake_ep = _fake_entry_point("external_sink", _DummyPlugin)

        class _FakeEntryPoints:
            def select(self, group: str) -> list[Any]:
                return [fake_ep] if group == "fapilog.sinks" else []

            def get(self, group: str, default: Any = None) -> list[Any]:
                return [fake_ep] if group == "fapilog.sinks" else []

        monkeypatch.setattr(
            loader.importlib.metadata, "entry_points", lambda: _FakeEntryPoints()
        )

        with pytest.raises(loader.PluginNotFoundError) as exc_info:
            loader.load_plugin(
                "fapilog.sinks", "external_sink", {}, allow_external=False, allowlist=[]
            )

        error_msg = str(exc_info.value)
        assert "external_sink" in error_msg
        assert "external plugins disabled" in error_msg.lower()
        assert "allow_external" in error_msg

    def test_entry_point_allowed_with_allow_external_true(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Entry point plugins load when allow_external=True."""
        monkeypatch.setattr(loader, "BUILTIN_SINKS", {})
        monkeypatch.setattr(loader, "BUILTIN_ALIASES", {})

        fake_ep = _fake_entry_point("external_sink", _DummyPlugin)

        class _FakeEntryPoints:
            def select(self, group: str) -> list[Any]:
                return [fake_ep] if group == "fapilog.sinks" else []

            def get(self, group: str, default: Any = None) -> list[Any]:
                return [fake_ep] if group == "fapilog.sinks" else []

        monkeypatch.setattr(
            loader.importlib.metadata, "entry_points", lambda: _FakeEntryPoints()
        )

        inst = loader.load_plugin(
            "fapilog.sinks", "external_sink", {}, allow_external=True, allowlist=[]
        )
        assert isinstance(inst, _DummyPlugin)

    def test_entry_point_allowed_when_in_allowlist(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Specific external plugins allowed via allowlist (implicit opt-in)."""
        monkeypatch.setattr(loader, "BUILTIN_SINKS", {})
        monkeypatch.setattr(loader, "BUILTIN_ALIASES", {})

        fake_ep = _fake_entry_point("my_custom_sink", _DummyPlugin)

        class _FakeEntryPoints:
            def select(self, group: str) -> list[Any]:
                return [fake_ep] if group == "fapilog.sinks" else []

            def get(self, group: str, default: Any = None) -> list[Any]:
                return [fake_ep] if group == "fapilog.sinks" else []

        monkeypatch.setattr(
            loader.importlib.metadata, "entry_points", lambda: _FakeEntryPoints()
        )

        # allow_external=False but plugin is in allowlist
        inst = loader.load_plugin(
            "fapilog.sinks",
            "my_custom_sink",
            {},
            allow_external=False,
            allowlist=["my_custom_sink"],
        )
        assert isinstance(inst, _DummyPlugin)

    def test_allowlist_normalizes_names(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Allowlist matching uses normalized names (hyphen/underscore agnostic)."""
        monkeypatch.setattr(loader, "BUILTIN_SINKS", {})
        monkeypatch.setattr(loader, "BUILTIN_ALIASES", {})

        fake_ep = _fake_entry_point("my-custom-sink", _DummyPlugin)

        class _FakeEntryPoints:
            def select(self, group: str) -> list[Any]:
                return [fake_ep] if group == "fapilog.sinks" else []

            def get(self, group: str, default: Any = None) -> list[Any]:
                return [fake_ep] if group == "fapilog.sinks" else []

        monkeypatch.setattr(
            loader.importlib.metadata, "entry_points", lambda: _FakeEntryPoints()
        )

        # Allowlist uses underscores, entry point uses hyphens
        inst = loader.load_plugin(
            "fapilog.sinks",
            "my-custom-sink",
            {},
            allow_external=False,
            allowlist=["my_custom_sink"],
        )
        assert isinstance(inst, _DummyPlugin)


class TestSettingsIntegration:
    """Verify settings are wired through to the loader."""

    def test_load_plugins_passes_allow_external_from_settings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_load_plugins passes allow_external from settings to load_plugin."""
        import fapilog

        monkeypatch.setattr(loader, "BUILTIN_SINKS", {})
        monkeypatch.setattr(loader, "BUILTIN_ALIASES", {})

        fake_ep = _fake_entry_point("external_sink", _DummyPlugin)

        class _FakeEntryPoints:
            def select(self, group: str) -> list[Any]:
                return [fake_ep] if group == "fapilog.sinks" else []

            def get(self, group: str, default: Any = None) -> list[Any]:
                return [fake_ep] if group == "fapilog.sinks" else []

        monkeypatch.setattr(
            loader.importlib.metadata, "entry_points", lambda: _FakeEntryPoints()
        )

        # With default settings (allow_external=False), external plugin is skipped
        settings = Settings()
        result = fapilog._load_plugins("fapilog.sinks", ["external_sink"], settings, {})
        # Plugin is not loaded due to security restriction
        assert len(result) == 0

    def test_load_plugins_allows_external_when_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_load_plugins loads external plugin when allow_external=True."""
        import fapilog

        monkeypatch.setattr(loader, "BUILTIN_SINKS", {})
        monkeypatch.setattr(loader, "BUILTIN_ALIASES", {})

        fake_ep = _fake_entry_point("external_sink", _DummyPlugin)

        class _FakeEntryPoints:
            def select(self, group: str) -> list[Any]:
                return [fake_ep] if group == "fapilog.sinks" else []

            def get(self, group: str, default: Any = None) -> list[Any]:
                return [fake_ep] if group == "fapilog.sinks" else []

        monkeypatch.setattr(
            loader.importlib.metadata, "entry_points", lambda: _FakeEntryPoints()
        )

        # With allow_external=True, external plugin loads
        settings = Settings(plugins={"allow_external": True})
        result = fapilog._load_plugins("fapilog.sinks", ["external_sink"], settings, {})
        assert len(result) == 1
        assert isinstance(result[0], _DummyPlugin)

    def test_load_plugins_allows_external_via_allowlist(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_load_plugins allows specific external plugin via allowlist."""
        import fapilog

        monkeypatch.setattr(loader, "BUILTIN_SINKS", {})
        monkeypatch.setattr(loader, "BUILTIN_ALIASES", {})

        fake_ep = _fake_entry_point("approved_sink", _DummyPlugin)

        class _FakeEntryPoints:
            def select(self, group: str) -> list[Any]:
                return [fake_ep] if group == "fapilog.sinks" else []

            def get(self, group: str, default: Any = None) -> list[Any]:
                return [fake_ep] if group == "fapilog.sinks" else []

        monkeypatch.setattr(
            loader.importlib.metadata, "entry_points", lambda: _FakeEntryPoints()
        )

        # With allowlist containing the plugin, it loads (implicit opt-in)
        settings = Settings(plugins={"allowlist": ["approved_sink"]})
        result = fapilog._load_plugins("fapilog.sinks", ["approved_sink"], settings, {})
        assert len(result) == 1
        assert isinstance(result[0], _DummyPlugin)


class TestExternalPluginWarning:
    """AC3: Warning emitted when loading external plugins."""

    def test_warning_emitted_on_external_plugin_load(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Loading an external plugin emits a diagnostic warning."""
        monkeypatch.setattr(loader, "BUILTIN_SINKS", {})
        monkeypatch.setattr(loader, "BUILTIN_ALIASES", {})

        fake_ep = _fake_entry_point("external_sink", _DummyPlugin)

        class _FakeEntryPoints:
            def select(self, group: str) -> list[Any]:
                return [fake_ep] if group == "fapilog.sinks" else []

            def get(self, group: str, default: Any = None) -> list[Any]:
                return [fake_ep] if group == "fapilog.sinks" else []

        monkeypatch.setattr(
            loader.importlib.metadata, "entry_points", lambda: _FakeEntryPoints()
        )

        warnings_emitted: list[dict[str, Any]] = []

        def capture_warn(component: str, message: str, **fields: Any) -> None:
            warnings_emitted.append(
                {"component": component, "message": message, **fields}
            )

        monkeypatch.setattr(loader.diagnostics, "warn", capture_warn)

        # Load external plugin with allow_external=True
        loader.load_plugin(
            "fapilog.sinks", "external_sink", {}, allow_external=True, allowlist=[]
        )

        # Verify warning was emitted
        assert len(warnings_emitted) == 1
        warning = warnings_emitted[0]
        assert warning["component"] == "plugins"
        assert "external" in warning["message"].lower()
        assert warning["name"] == "external_sink"
        assert warning["group"] == "fapilog.sinks"

    def test_no_warning_for_builtin_plugin(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Built-in plugins do not emit external plugin warning."""
        monkeypatch.setattr(loader, "BUILTIN_SINKS", {"console": _DummyPlugin})
        monkeypatch.setattr(loader, "BUILTIN_ALIASES", {"fapilog.sinks": {}})

        warnings_emitted: list[dict[str, Any]] = []

        def capture_warn(component: str, message: str, **fields: Any) -> None:
            warnings_emitted.append(
                {"component": component, "message": message, **fields}
            )

        monkeypatch.setattr(loader.diagnostics, "warn", capture_warn)

        # Load built-in plugin
        loader.load_plugin(
            "fapilog.sinks", "console", {}, allow_external=False, allowlist=[]
        )

        # No warning should be emitted for built-in plugins
        assert len(warnings_emitted) == 0

    def test_external_plugin_loads_when_diagnostics_fail(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """External plugin still loads even if diagnostics.warn fails."""
        monkeypatch.setattr(loader, "BUILTIN_SINKS", {})
        monkeypatch.setattr(loader, "BUILTIN_ALIASES", {})

        fake_ep = _fake_entry_point("external_sink", _DummyPlugin)

        class _FakeEntryPoints:
            def select(self, group: str) -> list[Any]:
                return [fake_ep] if group == "fapilog.sinks" else []

            def get(self, group: str, default: Any = None) -> list[Any]:
                return [fake_ep] if group == "fapilog.sinks" else []

        monkeypatch.setattr(
            loader.importlib.metadata, "entry_points", lambda: _FakeEntryPoints()
        )

        def failing_warn(component: str, message: str, **fields: Any) -> None:
            raise RuntimeError("diagnostics system failure")

        monkeypatch.setattr(loader.diagnostics, "warn", failing_warn)

        # Plugin should still load despite diagnostics failure
        inst = loader.load_plugin(
            "fapilog.sinks", "external_sink", {}, allow_external=True, allowlist=[]
        )
        assert isinstance(inst, _DummyPlugin)
