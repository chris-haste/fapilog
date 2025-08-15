from __future__ import annotations

"""
Plugin API contract versioning utilities.

This module defines the semantic API contract version used by plugin authoring
contracts (protocols) and provides helpers to parse and compare version tuples
for compatibility checks.

Compatibility policy (major.minor):
- Compatible if declared.major == current.major and declared.minor <= current.minor
- Otherwise incompatible
"""

# Note: Use built-in tuple annotations for type hints; avoid typing.Tuple

# Semantic version for the plugin API contracts exposed to authors
PLUGIN_API_VERSION: tuple[int, int] = (1, 0)


def parse_api_version(raw: str) -> tuple[int, int]:
    """Parse a semantic major.minor string into an integer tuple.

    Args:
        raw: Version string like "1.0" or "2.3".

    Returns:
        A tuple of (major, minor).

    Raises:
        ValueError: If the string is not in the expected "X.Y" format with
            non-negative integers.
    """
    parts = raw.strip().split(".")
    if len(parts) != 2:
        raise ValueError(f"Invalid api_version format: {raw!r}. Expected 'X.Y'.")
    try:
        major = int(parts[0])
        minor = int(parts[1])
    except Exception as exc:
        raise ValueError(f"Invalid api_version integers: {raw!r}.") from exc
    if major < 0 or minor < 0:
        raise ValueError(f"api_version must be non-negative: {raw!r}.")
    return (major, minor)


def is_plugin_api_compatible(
    declared: tuple[int, int], current: tuple[int, int] | None = None
) -> bool:
    """Return True if a declared API version is compatible with the current API.

    Compatibility policy:
    - major must match exactly
    - declared.minor must be less than or equal to current.minor
    """
    if current is None:
        current = PLUGIN_API_VERSION
    declared_major, declared_minor = int(declared[0]), int(declared[1])
    current_major, current_minor = int(current[0]), int(current[1])
    if declared_major != current_major:
        return False
    return declared_minor <= current_minor


# Mark as referenced for static analyzers (vulture)
_VULTURE_USED: tuple[object, ...] = (
    PLUGIN_API_VERSION,
    parse_api_version,
    is_plugin_api_compatible,
)
