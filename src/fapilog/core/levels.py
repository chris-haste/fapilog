"""Custom log level registry (Story 10.47).

This module provides the ability to register custom log levels beyond the
standard DEBUG, INFO, WARNING, ERROR, CRITICAL levels.

Custom levels must be registered before any loggers are created. Once a
logger is created, the registry is frozen and no new levels can be added.

Example:
    import fapilog

    # Register custom levels at module load time (before creating loggers)
    fapilog.register_level("TRACE", priority=5, add_method=True)
    fapilog.register_level("AUDIT", priority=25, add_method=True)

    # Now create loggers
    logger = fapilog.get_logger()
    logger.trace("entering function")  # dynamic method
    logger.audit("user login", user_id="123")
"""

from __future__ import annotations

from typing import Final

_DEFAULT_LEVELS: Final[dict[str, int]] = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "WARN": 30,  # alias
    "ERROR": 40,
    "CRITICAL": 50,
    "FATAL": 50,  # alias
    "AUDIT": 60,  # compliance/accountability records
    "SECURITY": 70,  # security-relevant events
}

_custom_levels: dict[str, int] = {}
_pending_methods: list[str] = []
_registry_frozen: bool = False


def register_level(
    name: str,
    priority: int,
    *,
    add_method: bool = False,
) -> None:
    """Register a custom log level.

    Must be called before any loggers are created.

    Args:
        name: Level name (e.g., "TRACE", "AUDIT"). Will be uppercased.
        priority: Numeric priority (0-99). Lower = more verbose.
                  Standard levels: DEBUG=10, INFO=20, WARNING=30, ERROR=40, CRITICAL=50
        add_method: If True, add a method to logger facades (e.g., logger.trace())

    Raises:
        ValueError: If name already exists or priority is invalid
        RuntimeError: If called after loggers have been created

    Example:
        >>> register_level("TRACE", priority=5, add_method=True)
        >>> register_level("AUDIT", priority=25, add_method=True)
    """
    global _registry_frozen

    if _registry_frozen:
        raise RuntimeError(
            "Cannot register levels after loggers have been created. "
            "Call register_level() at module load time."
        )

    name_upper = name.upper()

    if name_upper in _DEFAULT_LEVELS or name_upper in _custom_levels:
        raise ValueError(f"Level '{name_upper}' already exists")

    if not 0 <= priority <= 99:
        raise ValueError(f"Priority must be 0-99, got {priority}")

    _custom_levels[name_upper] = priority

    if add_method:
        _pending_methods.append(name_upper)


def get_level_priority(level: str) -> int:
    """Get priority for a level name.

    Args:
        level: Level name (case-insensitive)

    Returns:
        Priority value. Unknown levels default to INFO (20).
    """
    level_upper = level.upper()
    if level_upper in _custom_levels:
        return _custom_levels[level_upper]
    return _DEFAULT_LEVELS.get(level_upper, 20)  # default to INFO


def get_all_levels() -> dict[str, int]:
    """Get all registered levels (default + custom).

    Returns:
        Dict mapping level names to priorities.
    """
    return {**_DEFAULT_LEVELS, **_custom_levels}


def get_pending_methods() -> list[str]:
    """Get level names that should have logger methods generated.

    Returns:
        List of level names (uppercase) that were registered with add_method=True.
    """
    return list(_pending_methods)


def freeze_registry() -> None:
    """Freeze the registry, preventing new level registration.

    Called automatically when the first logger is created.
    """
    global _registry_frozen
    _registry_frozen = True


def is_registry_frozen() -> bool:
    """Check if the registry is frozen.

    Returns:
        True if no new levels can be registered.
    """
    return _registry_frozen


def _reset_registry() -> None:
    """Reset the registry to initial state (for testing only).

    Warning:
        This function is for testing purposes only. Do not use in production code.
    """
    global _registry_frozen
    _custom_levels.clear()
    _pending_methods.clear()
    _registry_frozen = False
