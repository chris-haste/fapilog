from __future__ import annotations

import asyncio
import os
from unittest.mock import patch

import pytest

import fapilog
from fapilog import Settings, get_logger
from fapilog.core.defaults import (
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
    def test_default_log_level_uses_tty(self) -> None:
        with patch("fapilog.core.defaults.is_ci_environment", return_value=False):
            with patch("fapilog.core.defaults.is_tty_environment", return_value=True):
                logger = get_logger()
                try:
                    assert logger._level_gate is None  # noqa: SLF001
                finally:
                    _drain_logger(logger)

    def test_default_log_level_non_tty(self) -> None:
        with patch("fapilog.core.defaults.is_ci_environment", return_value=False):
            with patch("fapilog.core.defaults.is_tty_environment", return_value=False):
                logger = get_logger()
                try:
                    assert logger._level_gate == LEVEL_PRIORITY["INFO"]  # noqa: SLF001
                finally:
                    _drain_logger(logger)

    def test_ci_overrides_tty_default(self) -> None:
        with patch("fapilog.core.defaults.is_ci_environment", return_value=True):
            with patch("fapilog.core.defaults.is_tty_environment", return_value=True):
                logger = get_logger()
                try:
                    assert logger._level_gate == LEVEL_PRIORITY["INFO"]  # noqa: SLF001
                finally:
                    _drain_logger(logger)

    def test_explicit_log_level_overrides_defaults(self) -> None:
        settings = Settings(core={"log_level": "ERROR"})
        with patch("fapilog.core.defaults.is_ci_environment", return_value=False):
            with patch("fapilog.core.defaults.is_tty_environment", return_value=True):
                logger = get_logger(settings=settings)
                try:
                    assert logger._level_gate == LEVEL_PRIORITY["ERROR"]  # noqa: SLF001
                finally:
                    _drain_logger(logger)

    def test_preset_log_level_overrides_defaults(self) -> None:
        with patch("fapilog.core.defaults.is_ci_environment", return_value=False):
            with patch("fapilog.core.defaults.is_tty_environment", return_value=True):
                logger = get_logger(preset="production")
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
