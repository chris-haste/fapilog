from __future__ import annotations

import os
import sys
from typing import Iterable

_CI_ENV_VARS: tuple[str, ...] = (
    "CI",
    "GITHUB_ACTIONS",
    "JENKINS_URL",
    "GITLAB_CI",
    "CIRCLECI",
    "TRAVIS",
    "TEAMCITY_VERSION",
)


def get_default_log_level(
    *, is_tty: bool | None = None, is_ci: bool | None = None
) -> str:
    """Return the default log level based on TTY/CI context."""
    if is_ci is None:
        is_ci = is_ci_environment()
    if is_ci:
        return "INFO"
    if is_tty is None:
        is_tty = is_tty_environment()
    return "DEBUG" if is_tty else "INFO"


def is_ci_environment(env_vars: Iterable[str] | None = None) -> bool:
    """Detect CI by checking for common environment variables."""
    vars_to_check = tuple(env_vars) if env_vars is not None else _CI_ENV_VARS
    return any(os.getenv(var) for var in vars_to_check)


def is_tty_environment() -> bool:
    """Return True when stdout is a TTY; False on errors."""
    try:
        return bool(sys.stdout.isatty())
    except Exception:
        return False


def should_fallback_sink(primary_failed: bool) -> bool:
    """Return True when a sink write failure should trigger fallback."""
    return bool(primary_failed)
