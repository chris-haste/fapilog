from __future__ import annotations

import os
import re
import sys
from typing import Iterable

# Minimal sensitive fields for fallback redaction (Story 4.46)
FALLBACK_SENSITIVE_FIELDS: frozenset[str] = frozenset(
    {
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
)

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


# Regex patterns for scrubbing secrets from raw (non-JSON) fallback output (Story 4.59)
# Complements FALLBACK_SENSITIVE_FIELDS which handles parseable JSON field names.
# Each pattern captures the key and separator, then replaces the value with ***.
# Value pattern [^\s&;]+ matches up to whitespace or common delimiters (& for URLs, ; for headers).
FALLBACK_SCRUB_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(password|passwd|pwd)(\s*[=:]\s*)[^\s&;]+", re.I), r"\1\2***"),
    (
        re.compile(r"(token|api_key|apikey|secret)(\s*[=:]\s*)[^\s&;]+", re.I),
        r"\1\2***",
    ),
    # Authorization headers may have spaces (e.g., "Bearer token"), match to end or delimiter
    (re.compile(r"(authorization|auth)(\s*[=:]\s*)[^\n&;]+", re.I), r"\1\2***"),
]
