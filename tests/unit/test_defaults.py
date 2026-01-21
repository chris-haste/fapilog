from __future__ import annotations

import asyncio
import os
from unittest.mock import patch

import pytest

import fapilog
from fapilog import Settings, get_logger
from fapilog.core.defaults import (
    FALLBACK_SENSITIVE_FIELDS,
    get_default_log_level,
    is_ci_environment,
    is_tty_environment,
    should_fallback_sink,
)
from fapilog.core.settings import CoreSettings
from fapilog.plugins.filters.level import LEVEL_PRIORITY


def _drain_logger(logger) -> None:
    asyncio.run(logger.stop_and_drain())


class TestGetDefaultLogLevel:
    def test_tty_returns_debug(self) -> None:
        assert get_default_log_level(is_tty=True, is_ci=False) == "DEBUG"

    def test_non_tty_returns_info(self) -> None:
        assert get_default_log_level(is_tty=False, is_ci=False) == "INFO"

    def test_ci_overrides_tty(self) -> None:
        assert get_default_log_level(is_tty=True, is_ci=True) == "INFO"

    def test_auto_detects_tty(self) -> None:
        with patch("sys.stdout.isatty", return_value=True):
            assert get_default_log_level(is_ci=False) == "DEBUG"

    def test_auto_detects_ci(self) -> None:
        with patch.dict(os.environ, {"CI": "true"}):
            assert get_default_log_level(is_tty=True) == "INFO"


class TestIsCiEnvironment:
    def test_ci_var_detected(self) -> None:
        with patch.dict(os.environ, {"CI": "true"}):
            assert is_ci_environment() is True

    def test_github_actions_detected(self) -> None:
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
            assert is_ci_environment() is True

    def test_jenkins_detected(self) -> None:
        with patch.dict(os.environ, {"JENKINS_URL": "http://jenkins"}):
            assert is_ci_environment() is True

    def test_no_ci_vars_returns_false(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            assert is_ci_environment() is False


class TestIsTtyEnvironment:
    def test_tty_detected(self) -> None:
        with patch("sys.stdout.isatty", return_value=True):
            assert is_tty_environment() is True

    def test_non_tty_detected(self) -> None:
        with patch("sys.stdout.isatty", return_value=False):
            assert is_tty_environment() is False

    def test_isatty_exception_returns_false(self) -> None:
        with patch("sys.stdout.isatty", side_effect=Exception):
            assert is_tty_environment() is False


class TestDefaultLogLevelIntegration:
    """Test Story 10.6 defaults (with auto_detect=False to isolate behavior)."""

    def test_default_log_level_uses_tty(self) -> None:
        with patch("fapilog.core.defaults.is_ci_environment", return_value=False):
            with patch("fapilog.core.defaults.is_tty_environment", return_value=True):
                # Use auto_detect=False and reuse=False to test defaults in isolation
                logger = get_logger(auto_detect=False, reuse=False)
                try:
                    assert logger._level_gate is None  # noqa: SLF001
                finally:
                    _drain_logger(logger)

    def test_default_log_level_non_tty(self) -> None:
        with patch("fapilog.core.defaults.is_ci_environment", return_value=False):
            with patch("fapilog.core.defaults.is_tty_environment", return_value=False):
                logger = get_logger(auto_detect=False, reuse=False)
                try:
                    assert logger._level_gate == LEVEL_PRIORITY["INFO"]  # noqa: SLF001
                finally:
                    _drain_logger(logger)

    def test_ci_overrides_tty_default(self) -> None:
        with patch("fapilog.core.defaults.is_ci_environment", return_value=True):
            with patch("fapilog.core.defaults.is_tty_environment", return_value=True):
                logger = get_logger(auto_detect=False, reuse=False)
                try:
                    assert logger._level_gate == LEVEL_PRIORITY["INFO"]  # noqa: SLF001
                finally:
                    _drain_logger(logger)

    def test_explicit_log_level_overrides_defaults(self) -> None:
        settings = Settings(core={"log_level": "ERROR"})
        with patch("fapilog.core.defaults.is_ci_environment", return_value=False):
            with patch("fapilog.core.defaults.is_tty_environment", return_value=True):
                logger = get_logger(settings=settings, reuse=False)
                try:
                    assert logger._level_gate == LEVEL_PRIORITY["ERROR"]  # noqa: SLF001
                finally:
                    _drain_logger(logger)

    def test_preset_log_level_overrides_defaults(self) -> None:
        with patch("fapilog.core.defaults.is_ci_environment", return_value=False):
            with patch("fapilog.core.defaults.is_tty_environment", return_value=True):
                logger = get_logger(preset="production", reuse=False)
                try:
                    assert logger._level_gate == LEVEL_PRIORITY["INFO"]  # noqa: SLF001
                finally:
                    _drain_logger(logger)


class TestShouldFallbackSink:
    def test_should_fallback_sink(self) -> None:
        assert should_fallback_sink(True) is True
        assert should_fallback_sink(False) is False


class TestApplyDefaultLogLevel:
    def test_env_log_level_treated_as_explicit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings = Settings()
        monkeypatch.setenv("FAPILOG_CORE__LOG_LEVEL", "DEBUG")
        with patch(
            "fapilog.core.defaults.get_default_log_level",
            side_effect=AssertionError("should not be called"),
        ):
            updated = fapilog._apply_default_log_level(settings, preset=None)

        assert updated is settings

    def test_model_fields_set_exception_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _raise(_self) -> set[str]:
            raise RuntimeError("boom")

        monkeypatch.setattr(
            CoreSettings, "model_fields_set", property(_raise), raising=False
        )
        settings = Settings()
        with patch("fapilog.core.defaults.get_default_log_level", return_value="INFO"):
            updated = fapilog._apply_default_log_level(settings, preset=None)

        assert updated is not settings
        assert updated.core.log_level == "INFO"


class TestFallbackSensitiveFields:
    """Test FALLBACK_SENSITIVE_FIELDS constant (Story 4.46)."""

    def test_is_frozenset(self) -> None:
        assert isinstance(FALLBACK_SENSITIVE_FIELDS, frozenset)

    def test_contains_common_sensitive_fields(self) -> None:
        expected = {
            "password",
            "passwd",
            "secret",
            "token",
            "api_key",
            "apikey",
            "api_secret",
            "apisecret",
            "authorization",
            "auth",
            "credential",
            "credentials",
            "private_key",
            "privatekey",
            "access_token",
            "refresh_token",
        }
        assert expected.issubset(FALLBACK_SENSITIVE_FIELDS)

    def test_values_are_lowercase(self) -> None:
        for field in FALLBACK_SENSITIVE_FIELDS:
            assert field == field.lower(), f"Field '{field}' is not lowercase"


class TestFallbackRedactModeDefault:
    """Test fallback_redact_mode default value (Story 4.46 AC5)."""

    def test_default_is_minimal(self) -> None:
        settings = Settings()
        assert settings.core.fallback_redact_mode == "minimal"

    def test_accepts_inherit_mode(self) -> None:
        settings = Settings(core={"fallback_redact_mode": "inherit"})
        assert settings.core.fallback_redact_mode == "inherit"

    def test_accepts_none_mode(self) -> None:
        settings = Settings(core={"fallback_redact_mode": "none"})
        assert settings.core.fallback_redact_mode == "none"

    def test_rejects_invalid_mode(self) -> None:
        with pytest.raises(ValueError, match="Input should be"):
            Settings(core={"fallback_redact_mode": "invalid"})
