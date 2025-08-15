from __future__ import annotations

import pytest

from fapilog.plugins.versioning import (
    PLUGIN_API_VERSION,
    is_plugin_api_compatible,
    parse_api_version,
)


class TestPluginApiVersioning:
    def test_parse_api_version_valid(self) -> None:
        assert parse_api_version("1.0") == (1, 0)
        assert parse_api_version("2.3") == (2, 3)
        # Whitespace tolerance
        assert parse_api_version(" 1.2 ") == (1, 2)

    def test_parse_api_version_invalid_format(self) -> None:
        with pytest.raises(ValueError):
            parse_api_version("1")
        with pytest.raises(ValueError):
            parse_api_version("1.2.3")
        with pytest.raises(ValueError):
            parse_api_version("a.b")

    def test_parse_api_version_negative(self) -> None:
        with pytest.raises(ValueError):
            parse_api_version("-1.0")
        with pytest.raises(ValueError):
            parse_api_version("1.-1")

    def test_is_plugin_api_compatible_with_default_current(self) -> None:
        # Using default current (PLUGIN_API_VERSION)
        major, minor = PLUGIN_API_VERSION
        assert is_plugin_api_compatible((major, minor)) is True
        # Lower minor declared is compatible
        if minor > 0:
            assert is_plugin_api_compatible((major, minor - 1)) is True
        # Higher minor declared is incompatible
        assert is_plugin_api_compatible((major, minor + 1)) is False

    def test_is_plugin_api_compatible_with_explicit_current(self) -> None:
        # Same major, lower/equal minor => compatible
        assert is_plugin_api_compatible((1, 0), (1, 0)) is True
        assert is_plugin_api_compatible((1, 0), (1, 1)) is True
        assert is_plugin_api_compatible((1, 1), (1, 1)) is True
        # Same major, higher minor declared => incompatible
        assert is_plugin_api_compatible((1, 2), (1, 1)) is False
        # Different major => incompatible
        assert is_plugin_api_compatible((2, 0), (1, 9)) is False
