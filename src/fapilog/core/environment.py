"""Smart environment auto-detection (Story 10.8).

Provides comprehensive environment detection for automatic logger configuration.
Detects: Lambda, Kubernetes, Docker, CI, and Local environments.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from .defaults import is_ci_environment

EnvironmentType = Literal["local", "docker", "kubernetes", "lambda", "ci"]

# Path constants (allow mocking in tests)
_K8S_SA_PATH = Path("/var/run/secrets/kubernetes.io/serviceaccount")
_DOCKERENV_PATH = Path("/.dockerenv")
_CGROUP_PATH = Path("/proc/1/cgroup")

# Module-level cache for detection result
_ENV_CACHE: EnvironmentType | None = None


def detect_environment(*, use_cache: bool = True) -> EnvironmentType:
    """Detect deployment environment.

    Detection priority order (highest to lowest):
    1. Lambda (AWS_LAMBDA_FUNCTION_NAME env var)
    2. Kubernetes (serviceaccount path or POD_NAME env var)
    3. Docker (/.dockerenv file or /proc/1/cgroup contains "docker")
    4. CI (uses is_ci_environment() from Story 10.6)
    5. Local (default)

    Args:
        use_cache: Use cached result if available (default True).
            Set to False to force re-detection.

    Returns:
        Detected environment type.
    """
    global _ENV_CACHE
    if use_cache and _ENV_CACHE is not None:
        return _ENV_CACHE

    # Priority 1: Lambda (highest - Lambda can run in containers)
    if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        result: EnvironmentType = "lambda"
        _ENV_CACHE = result
        return result

    # Priority 2: Kubernetes
    if _detect_kubernetes():
        result = "kubernetes"
        _ENV_CACHE = result
        return result

    # Priority 3: Docker
    if _detect_docker():
        result = "docker"
        _ENV_CACHE = result
        return result

    # Priority 4: CI (uses Story 10.6 helper)
    if is_ci_environment():
        result = "ci"
        _ENV_CACHE = result
        return result

    # Priority 5: Local (default)
    result = "local"
    _ENV_CACHE = result
    return result


def _detect_kubernetes() -> bool:
    """Detect Kubernetes environment.

    Uses two detection methods:
    1. Service account path (most reliable - only exists in K8s pods)
    2. POD_NAME env var (common in K8s deployments via Downward API)

    Returns:
        True if running in Kubernetes, False otherwise.
    """
    # Method 1: Service account path (most reliable)
    if _K8S_SA_PATH.exists():
        return True

    # Method 2: POD_NAME env var (common in K8s via Downward API)
    if os.getenv("POD_NAME"):
        return True

    return False


def _detect_docker() -> bool:
    """Detect Docker environment.

    Uses two detection methods:
    1. /.dockerenv file (Docker creates this file in containers)
    2. /proc/1/cgroup contains "docker" (checks cgroup hierarchy)

    Note: This may also match in Kubernetes pods (which run in containers),
    but Kubernetes detection takes priority in detect_environment().

    Returns:
        True if running in Docker, False otherwise.
    """
    # Method 1: /.dockerenv file (Docker-specific)
    if _DOCKERENV_PATH.exists():
        return True

    # Method 2: /proc/1/cgroup contains "docker"
    try:
        if _CGROUP_PATH.exists():
            content = _CGROUP_PATH.read_text()
            if "docker" in content.lower():
                return True
    except (OSError, PermissionError, UnicodeDecodeError):
        # Handle cases where file doesn't exist, can't be read, or has binary data
        pass

    return False


def get_environment_config(env: EnvironmentType) -> dict[str, Any]:
    """Get configuration for detected environment.

    Returns Settings-compatible dict with environment-specific settings.
    Designed to be merged with Story 10.6 defaults.

    Args:
        env: Environment type to get config for.

    Returns:
        Configuration dict with 'core' and 'enrichers' keys.
    """
    configs: dict[EnvironmentType, dict[str, Any]] = {
        "lambda": {
            "core": {
                "log_level": "INFO",
                "batch_max_size": 10,  # Smaller batches for Lambda timeouts
                "batch_timeout_seconds": 0.1,  # Faster flushing
                "max_queue_size": 1000,  # Smaller queue for Lambda memory
            },
            "enrichers": [
                "runtime_info"
            ],  # Lambda-specific enricher not yet implemented
        },
        "kubernetes": {
            "core": {
                "log_level": "INFO",
            },
            "enrichers": ["runtime_info", "kubernetes"],  # Auto-enable K8s enricher
        },
        "docker": {
            "core": {
                "log_level": "INFO",
            },
            "enrichers": ["runtime_info"],  # Container metadata via runtime_info
        },
        "ci": {
            "core": {
                "log_level": "INFO",
            },
            "enrichers": ["runtime_info"],
        },
        "local": {
            # No log_level override - uses Story 10.6 defaults (DEBUG if TTY)
            "enrichers": ["runtime_info"],
        },
    }
    return configs.get(env, {"enrichers": ["runtime_info"]})


__all__ = [
    "EnvironmentType",
    "detect_environment",
    "get_environment_config",
]
