"""Integration tests for auto-configuration (Story 10.8)."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from fapilog import Settings, get_async_logger, get_logger
from fapilog.core import environment as env_module
from fapilog.plugins.filters.level import LEVEL_PRIORITY


def _drain_logger(logger) -> None:
    asyncio.run(logger.stop_and_drain())


@pytest.fixture(autouse=True)
def clear_env_cache():
    """Clear environment detection cache before each test."""
    env_module._ENV_CACHE = None
    yield
    env_module._ENV_CACHE = None


class TestAutoDetectParameter:
    """Test auto_detect parameter in get_logger()."""

    def test_auto_detect_true_detects_lambda(self) -> None:
        """auto_detect=True detects Lambda environment."""
        with patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": "my-function"}):
            with patch(
                "fapilog.core.environment._K8S_SA_PATH",
                Path("/nonexistent/path"),
            ):
                with patch(
                    "fapilog.core.environment._DOCKERENV_PATH",
                    Path("/nonexistent/.dockerenv"),
                ):
                    with patch(
                        "fapilog.core.environment._CGROUP_PATH",
                        Path("/nonexistent/cgroup"),
                    ):
                        logger = get_logger(auto_detect=True)
                        try:
                            # Lambda should set INFO level
                            assert logger._level_gate == LEVEL_PRIORITY["INFO"]
                        finally:
                            _drain_logger(logger)

    def test_auto_detect_true_detects_kubernetes(self) -> None:
        """auto_detect=True detects Kubernetes and enables enricher."""
        with patch.dict(os.environ, {"POD_NAME": "my-pod-abc123"}, clear=True):
            with patch(
                "fapilog.core.environment._K8S_SA_PATH",
                Path("/nonexistent/path"),
            ):
                with patch(
                    "fapilog.core.environment._DOCKERENV_PATH",
                    Path("/nonexistent/.dockerenv"),
                ):
                    with patch(
                        "fapilog.core.environment._CGROUP_PATH",
                        Path("/nonexistent/cgroup"),
                    ):
                        logger = get_logger(auto_detect=True)
                        try:
                            # K8s should set INFO level
                            assert logger._level_gate == LEVEL_PRIORITY["INFO"]
                            # Should have kubernetes enricher enabled
                            enricher_names = [
                                getattr(e, "name", type(e).__name__)
                                for e in logger._enrichers
                            ]
                            assert "kubernetes" in enricher_names
                        finally:
                            _drain_logger(logger)

    def test_auto_detect_false_uses_defaults_only(self) -> None:
        """auto_detect=False uses Story 10.6 defaults only."""
        with patch.dict(os.environ, {"POD_NAME": "my-pod"}, clear=True):
            with patch(
                "fapilog.core.environment._K8S_SA_PATH",
                Path("/nonexistent/path"),
            ):
                with patch(
                    "fapilog.core.defaults.is_ci_environment", return_value=False
                ):
                    with patch(
                        "fapilog.core.defaults.is_tty_environment", return_value=True
                    ):
                        logger = get_logger(auto_detect=False)
                        try:
                            # Should use TTY default (DEBUG) not K8s config
                            assert logger._level_gate is None  # DEBUG has no gate
                        finally:
                            _drain_logger(logger)

    def test_auto_detect_default_is_true(self) -> None:
        """auto_detect defaults to True when no explicit settings."""
        with patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": "func"}, clear=True):
            with patch(
                "fapilog.core.environment._K8S_SA_PATH",
                Path("/nonexistent/path"),
            ):
                with patch(
                    "fapilog.core.environment._DOCKERENV_PATH",
                    Path("/nonexistent/.dockerenv"),
                ):
                    with patch(
                        "fapilog.core.environment._CGROUP_PATH",
                        Path("/nonexistent/cgroup"),
                    ):
                        # No auto_detect param - should default to True
                        logger = get_logger()
                        try:
                            assert logger._level_gate == LEVEL_PRIORITY["INFO"]
                        finally:
                            _drain_logger(logger)


class TestEnvironmentParameter:
    """Test environment parameter in get_logger()."""

    def test_explicit_environment_overrides_detection(self) -> None:
        """Explicit environment parameter overrides auto-detection."""
        with patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": "func"}):
            # Even though Lambda is detected, use kubernetes config
            logger = get_logger(environment="kubernetes")
            try:
                # Should have kubernetes enricher enabled
                enricher_names = [
                    getattr(e, "name", type(e).__name__) for e in logger._enrichers
                ]
                assert "kubernetes" in enricher_names
            finally:
                _drain_logger(logger)

    def test_environment_lambda(self) -> None:
        """environment='lambda' applies Lambda config."""
        with patch.dict(os.environ, {}, clear=True):
            logger = get_logger(environment="lambda")
            try:
                assert logger._level_gate == LEVEL_PRIORITY["INFO"]
            finally:
                _drain_logger(logger)

    def test_environment_docker(self) -> None:
        """environment='docker' applies Docker config."""
        with patch.dict(os.environ, {}, clear=True):
            logger = get_logger(environment="docker")
            try:
                assert logger._level_gate == LEVEL_PRIORITY["INFO"]
            finally:
                _drain_logger(logger)

    def test_environment_ci(self) -> None:
        """environment='ci' applies CI config."""
        with patch.dict(os.environ, {}, clear=True):
            logger = get_logger(environment="ci")
            try:
                assert logger._level_gate == LEVEL_PRIORITY["INFO"]
            finally:
                _drain_logger(logger)

    def test_environment_local_uses_defaults(self) -> None:
        """environment='local' uses Story 10.6 defaults."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("fapilog.core.defaults.is_ci_environment", return_value=False):
                with patch(
                    "fapilog.core.defaults.is_tty_environment", return_value=True
                ):
                    logger = get_logger(environment="local")
                    try:
                        # Local + TTY = DEBUG (no gate)
                        assert logger._level_gate is None
                    finally:
                        _drain_logger(logger)


class TestParameterPriority:
    """Test parameter priority order."""

    def test_explicit_settings_disables_auto_detect(self) -> None:
        """Explicit settings parameter disables auto-detection."""
        settings = Settings(core={"log_level": "ERROR"})
        with patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": "func"}):
            logger = get_logger(settings=settings)
            try:
                # Should use explicit ERROR, not Lambda's INFO
                assert logger._level_gate == LEVEL_PRIORITY["ERROR"]
            finally:
                _drain_logger(logger)

    def test_explicit_preset_disables_auto_detect(self) -> None:
        """Explicit preset parameter disables auto-detection."""
        with patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": "func"}):
            logger = get_logger(preset="dev")
            try:
                # dev preset uses DEBUG level
                assert logger._level_gate is None  # DEBUG has no gate
            finally:
                _drain_logger(logger)

    def test_environment_takes_priority_over_auto_detect(self) -> None:
        """Explicit environment overrides auto-detection."""
        with patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": "func"}):
            logger = get_logger(environment="docker")
            try:
                # Should use docker config, not auto-detected lambda
                # Both have INFO, but docker shouldn't have lambda's batch settings
                assert logger._level_gate == LEVEL_PRIORITY["INFO"]
            finally:
                _drain_logger(logger)


class TestLambdaOptimizations:
    """Test Lambda-specific optimizations (AC5)."""

    def test_lambda_batch_settings(self) -> None:
        """Lambda environment gets optimized batch settings."""
        with patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": "func"}, clear=True):
            with patch(
                "fapilog.core.environment._K8S_SA_PATH",
                Path("/nonexistent/path"),
            ):
                with patch(
                    "fapilog.core.environment._DOCKERENV_PATH",
                    Path("/nonexistent/.dockerenv"),
                ):
                    with patch(
                        "fapilog.core.environment._CGROUP_PATH",
                        Path("/nonexistent/cgroup"),
                    ):
                        logger = get_logger(auto_detect=True)
                        try:
                            # Lambda optimizations
                            assert logger._batch_max_size == 10
                            assert logger._batch_timeout_seconds == 0.1
                            assert logger._queue.capacity == 1000
                        finally:
                            _drain_logger(logger)


class TestAsyncLogger:
    """Test auto-detection with async logger."""

    @pytest.mark.asyncio
    async def test_async_logger_auto_detect(self) -> None:
        """get_async_logger() supports auto_detect parameter."""
        with patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": "func"}, clear=True):
            with patch(
                "fapilog.core.environment._K8S_SA_PATH",
                Path("/nonexistent/path"),
            ):
                with patch(
                    "fapilog.core.environment._DOCKERENV_PATH",
                    Path("/nonexistent/.dockerenv"),
                ):
                    with patch(
                        "fapilog.core.environment._CGROUP_PATH",
                        Path("/nonexistent/cgroup"),
                    ):
                        logger = await get_async_logger(auto_detect=True)
                        try:
                            assert logger._level_gate == LEVEL_PRIORITY["INFO"]
                        finally:
                            await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_async_logger_environment_param(self) -> None:
        """get_async_logger() supports environment parameter."""
        with patch.dict(os.environ, {}, clear=True):
            logger = await get_async_logger(environment="kubernetes")
            try:
                enricher_names = [
                    getattr(e, "name", type(e).__name__) for e in logger._enrichers
                ]
                assert "kubernetes" in enricher_names
            finally:
                await logger.stop_and_drain()


class TestMutualExclusivity:
    """Test mutual exclusivity of parameters."""

    def test_environment_and_settings_mutually_exclusive(self) -> None:
        """Cannot specify both environment and settings."""
        settings = Settings()
        with pytest.raises(ValueError, match="Cannot specify both"):
            get_logger(environment="lambda", settings=settings)

    def test_environment_and_preset_mutually_exclusive(self) -> None:
        """Cannot specify both environment and preset."""
        with pytest.raises(ValueError, match="Cannot specify both"):
            get_logger(environment="lambda", preset="dev")
