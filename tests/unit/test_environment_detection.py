"""Unit tests for environment detection (Story 10.8)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from fapilog.core.environment import (
    EnvironmentType,
    detect_environment,
    get_environment_config,
)


class TestDetectLambda:
    """Test Lambda environment detection."""

    def test_lambda_detected_via_env_var(self) -> None:
        """Lambda detected via AWS_LAMBDA_FUNCTION_NAME."""
        with patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": "my-function"}):
            result = detect_environment(use_cache=False)
            assert result == "lambda"

    def test_no_lambda_env_var_not_detected(self) -> None:
        """No Lambda env var does not detect lambda."""
        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "fapilog.core.environment._detect_kubernetes", return_value=False
            ):
                with patch(
                    "fapilog.core.environment._detect_docker", return_value=False
                ):
                    with patch(
                        "fapilog.core.environment.is_ci_environment", return_value=False
                    ):
                        result = detect_environment(use_cache=False)
                        assert result != "lambda"


class TestDetectKubernetes:
    """Test Kubernetes environment detection."""

    def test_k8s_detected_via_serviceaccount_path(self, tmp_path: Path) -> None:
        """Kubernetes detected via serviceaccount path."""
        sa_path = (
            tmp_path / "var" / "run" / "secrets" / "kubernetes.io" / "serviceaccount"
        )
        sa_path.mkdir(parents=True, exist_ok=True)

        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "fapilog.core.environment._K8S_SA_PATH",
                sa_path,
            ):
                result = detect_environment(use_cache=False)
                assert result == "kubernetes"

    def test_k8s_detected_via_pod_name_env(self) -> None:
        """Kubernetes detected via POD_NAME env var."""
        with patch.dict(os.environ, {"POD_NAME": "my-pod-abc123"}, clear=True):
            result = detect_environment(use_cache=False)
            assert result == "kubernetes"

    def test_no_k8s_indicators_not_detected(self) -> None:
        """No Kubernetes indicators does not detect kubernetes."""
        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "fapilog.core.environment._K8S_SA_PATH",
                Path("/nonexistent/path"),
            ):
                with patch(
                    "fapilog.core.environment._detect_docker", return_value=False
                ):
                    with patch(
                        "fapilog.core.environment.is_ci_environment", return_value=False
                    ):
                        result = detect_environment(use_cache=False)
                        assert result != "kubernetes"


class TestDetectDocker:
    """Test Docker environment detection."""

    def test_docker_detected_via_dockerenv(self, tmp_path: Path) -> None:
        """Docker detected via /.dockerenv file."""
        dockerenv = tmp_path / ".dockerenv"
        dockerenv.touch()

        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "fapilog.core.environment._DOCKERENV_PATH",
                dockerenv,
            ):
                with patch(
                    "fapilog.core.environment._K8S_SA_PATH",
                    Path("/nonexistent/path"),
                ):
                    with patch(
                        "fapilog.core.environment._CGROUP_PATH",
                        Path("/nonexistent/cgroup"),
                    ):
                        result = detect_environment(use_cache=False)
                        assert result == "docker"

    def test_docker_detected_via_cgroup(self, tmp_path: Path) -> None:
        """Docker detected via /proc/1/cgroup containing docker."""
        cgroup = tmp_path / "cgroup"
        cgroup.write_text("1:name=systemd:/docker/abc123def456\n")

        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "fapilog.core.environment._DOCKERENV_PATH",
                Path("/nonexistent/.dockerenv"),
            ):
                with patch(
                    "fapilog.core.environment._K8S_SA_PATH",
                    Path("/nonexistent/path"),
                ):
                    with patch(
                        "fapilog.core.environment._CGROUP_PATH",
                        cgroup,
                    ):
                        result = detect_environment(use_cache=False)
                        assert result == "docker"

    def test_no_docker_indicators_not_detected(self) -> None:
        """No Docker indicators does not detect docker."""
        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "fapilog.core.environment._DOCKERENV_PATH",
                Path("/nonexistent/.dockerenv"),
            ):
                with patch(
                    "fapilog.core.environment._K8S_SA_PATH",
                    Path("/nonexistent/path"),
                ):
                    with patch(
                        "fapilog.core.environment._CGROUP_PATH",
                        Path("/nonexistent/cgroup"),
                    ):
                        with patch(
                            "fapilog.core.environment.is_ci_environment",
                            return_value=False,
                        ):
                            result = detect_environment(use_cache=False)
                            assert result != "docker"


class TestDetectCI:
    """Test CI environment detection."""

    def test_ci_detected_via_ci_var(self) -> None:
        """CI detected when CI env var present."""
        with patch.dict(os.environ, {"CI": "true"}, clear=True):
            with patch(
                "fapilog.core.environment._DOCKERENV_PATH",
                Path("/nonexistent/.dockerenv"),
            ):
                with patch(
                    "fapilog.core.environment._K8S_SA_PATH",
                    Path("/nonexistent/path"),
                ):
                    with patch(
                        "fapilog.core.environment._CGROUP_PATH",
                        Path("/nonexistent/cgroup"),
                    ):
                        result = detect_environment(use_cache=False)
                        assert result == "ci"

    def test_ci_detected_via_github_actions(self) -> None:
        """CI detected when GITHUB_ACTIONS env var present."""
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=True):
            with patch(
                "fapilog.core.environment._DOCKERENV_PATH",
                Path("/nonexistent/.dockerenv"),
            ):
                with patch(
                    "fapilog.core.environment._K8S_SA_PATH",
                    Path("/nonexistent/path"),
                ):
                    with patch(
                        "fapilog.core.environment._CGROUP_PATH",
                        Path("/nonexistent/cgroup"),
                    ):
                        result = detect_environment(use_cache=False)
                        assert result == "ci"


class TestDetectLocal:
    """Test local environment detection (default)."""

    def test_local_is_default(self) -> None:
        """Local is the default when no indicators present."""
        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "fapilog.core.environment._DOCKERENV_PATH",
                Path("/nonexistent/.dockerenv"),
            ):
                with patch(
                    "fapilog.core.environment._K8S_SA_PATH",
                    Path("/nonexistent/path"),
                ):
                    with patch(
                        "fapilog.core.environment._CGROUP_PATH",
                        Path("/nonexistent/cgroup"),
                    ):
                        result = detect_environment(use_cache=False)
                        assert result == "local"


class TestDetectionPriority:
    """Test environment detection priority order."""

    def test_lambda_takes_priority_over_kubernetes(self) -> None:
        """Lambda detection takes priority over Kubernetes."""
        with patch.dict(
            os.environ,
            {"AWS_LAMBDA_FUNCTION_NAME": "func", "POD_NAME": "pod"},
        ):
            result = detect_environment(use_cache=False)
            assert result == "lambda"

    def test_kubernetes_takes_priority_over_docker(self) -> None:
        """Kubernetes detection takes priority over Docker."""
        with patch.dict(os.environ, {"POD_NAME": "my-pod"}, clear=True):
            with patch("fapilog.core.environment._detect_docker", return_value=True):
                result = detect_environment(use_cache=False)
                assert result == "kubernetes"

    def test_docker_takes_priority_over_ci(self) -> None:
        """Docker detection takes priority over CI."""
        with patch.dict(os.environ, {"CI": "true"}, clear=True):
            with patch(
                "fapilog.core.environment._K8S_SA_PATH",
                Path("/nonexistent/path"),
            ):
                with patch(
                    "fapilog.core.environment._detect_docker", return_value=True
                ):
                    result = detect_environment(use_cache=False)
                    assert result == "docker"


class TestDetectionCaching:
    """Test detection result caching."""

    def test_detection_is_cached(self) -> None:
        """Detection results are cached by default."""
        from fapilog.core import environment

        # Clear any existing cache
        environment._ENV_CACHE = None

        with patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": "func"}):
            result1 = detect_environment(use_cache=True)
            assert result1 == "lambda"

        # Clear env but cache should still return lambda
        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "fapilog.core.environment._DOCKERENV_PATH",
                Path("/nonexistent/.dockerenv"),
            ):
                with patch(
                    "fapilog.core.environment._K8S_SA_PATH",
                    Path("/nonexistent/path"),
                ):
                    with patch(
                        "fapilog.core.environment._CGROUP_PATH",
                        Path("/nonexistent/cgroup"),
                    ):
                        result2 = detect_environment(use_cache=True)
                        assert result2 == "lambda"  # Still cached

        # Clean up
        environment._ENV_CACHE = None

    def test_cache_can_be_bypassed(self) -> None:
        """Cache can be bypassed with use_cache=False."""
        from fapilog.core import environment

        # Clear any existing cache
        environment._ENV_CACHE = None

        with patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": "func"}):
            detect_environment(use_cache=True)  # Cache as lambda

        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "fapilog.core.environment._DOCKERENV_PATH",
                Path("/nonexistent/.dockerenv"),
            ):
                with patch(
                    "fapilog.core.environment._K8S_SA_PATH",
                    Path("/nonexistent/path"),
                ):
                    with patch(
                        "fapilog.core.environment._CGROUP_PATH",
                        Path("/nonexistent/cgroup"),
                    ):
                        result = detect_environment(use_cache=False)
                        assert result == "local"  # Re-detected as local

        # Clean up
        environment._ENV_CACHE = None


class TestGetEnvironmentConfig:
    """Test get_environment_config() function."""

    def test_lambda_config(self) -> None:
        """Lambda config has optimized batch settings."""
        config = get_environment_config("lambda")
        assert config["core"]["log_level"] == "INFO"
        assert config["core"]["batch_max_size"] == 10
        assert config["core"]["batch_timeout_seconds"] == 0.1
        assert config["core"]["max_queue_size"] == 1000
        assert "runtime_info" in config["enrichers"]

    def test_kubernetes_config(self) -> None:
        """Kubernetes config auto-enables kubernetes enricher."""
        config = get_environment_config("kubernetes")
        assert config["core"]["log_level"] == "INFO"
        assert "kubernetes" in config["enrichers"]
        assert "runtime_info" in config["enrichers"]

    def test_docker_config(self) -> None:
        """Docker config uses runtime_info enricher."""
        config = get_environment_config("docker")
        assert config["core"]["log_level"] == "INFO"
        assert "runtime_info" in config["enrichers"]

    def test_ci_config(self) -> None:
        """CI config uses INFO level."""
        config = get_environment_config("ci")
        assert config["core"]["log_level"] == "INFO"
        assert "runtime_info" in config["enrichers"]

    def test_local_config(self) -> None:
        """Local config uses defaults (no log_level override)."""
        config = get_environment_config("local")
        assert "log_level" not in config.get("core", {})
        assert "runtime_info" in config["enrichers"]


class TestEnvironmentType:
    """Test EnvironmentType type alias."""

    def test_environment_type_values(self) -> None:
        """EnvironmentType includes all expected values."""
        valid_types: list[EnvironmentType] = [
            "local",
            "docker",
            "kubernetes",
            "lambda",
            "ci",
        ]
        for env_type in valid_types:
            # Should not raise type errors
            assert isinstance(env_type, str)
