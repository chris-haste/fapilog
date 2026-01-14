"""Unit tests for conftest.py helper functions."""

import pytest

from conftest import get_test_timeout


class TestGetTestTimeout:
    """Tests for the CI timeout multiplier helper."""

    def test_default_returns_base_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without env var, returns the base timeout unchanged."""
        monkeypatch.delenv("CI_TIMEOUT_MULTIPLIER", raising=False)
        assert get_test_timeout(0.1) == 0.1

    def test_applies_multiplier_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With multiplier set, scales the base timeout."""
        monkeypatch.setenv("CI_TIMEOUT_MULTIPLIER", "3")
        assert get_test_timeout(0.1) == pytest.approx(0.3)

    def test_multiplier_capped_at_max(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Multiplier is capped at max_multiplier (default 5x) to prevent hangs."""
        monkeypatch.setenv("CI_TIMEOUT_MULTIPLIER", "100")
        assert get_test_timeout(0.1) == pytest.approx(0.5)  # 0.1 * 5 max

    def test_custom_max_multiplier(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Can specify a custom max multiplier."""
        monkeypatch.setenv("CI_TIMEOUT_MULTIPLIER", "10")
        assert get_test_timeout(0.1, max_multiplier=3.0) == pytest.approx(0.3)

    def test_invalid_env_value_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Invalid multiplier value falls back to 1.0."""
        monkeypatch.setenv("CI_TIMEOUT_MULTIPLIER", "invalid")
        assert get_test_timeout(0.1) == 0.1

    def test_empty_env_value_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty string falls back to 1.0."""
        monkeypatch.setenv("CI_TIMEOUT_MULTIPLIER", "")
        assert get_test_timeout(0.1) == 0.1

    def test_fractional_multiplier(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Fractional multipliers work (e.g., for faster local testing)."""
        monkeypatch.setenv("CI_TIMEOUT_MULTIPLIER", "0.5")
        assert get_test_timeout(1.0) == pytest.approx(0.5)

    def test_zero_base_returns_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Zero base timeout returns zero regardless of multiplier."""
        monkeypatch.setenv("CI_TIMEOUT_MULTIPLIER", "3")
        assert get_test_timeout(0.0) == 0.0
