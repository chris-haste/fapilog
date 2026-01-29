"""Pydantic v2 Annotated types for human-readable configuration values."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import BeforeValidator

SIZE_UNITS = {
    "b": 1,
    "kb": 1024,
    "mb": 1024**2,
    "gb": 1024**3,
    "tb": 1024**4,
}

DURATION_UNITS = {
    "ms": 0.001,
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
    "w": 604800,
}

ROTATION_INTERVALS = {
    "hourly": 3600,
    "daily": 86400,
    "weekly": 604800,
}

SIZE_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)\s*([kmgt]?b)$", re.IGNORECASE)
DURATION_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)\s*(ms|[smhdw])$", re.IGNORECASE)


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1].strip()
    return value


def _parse_size(value: str | int | None) -> int | None:
    """Parse size string to bytes."""
    if value is None:
        return None

    if isinstance(value, int):
        if value < 0:
            raise ValueError("Size must be non-negative")
        return value

    raw_value = str(value).strip()
    value_str = _strip_quotes(raw_value)
    negative = value_str.startswith("-")
    if negative:
        value_str = value_str[1:].strip()

    if value_str.isdigit():
        if negative:
            raise ValueError("Size must be non-negative")
        return int(value_str)

    match = SIZE_PATTERN.match(value_str)
    if not match:
        raise ValueError(
            f"Invalid size format: '{raw_value}'. "
            "Use format like '10 MB' (units: KB, MB, GB, TB)"
        )

    number_str, unit_str = match.groups()
    number = float(number_str)
    multiplier = SIZE_UNITS[unit_str.lower()]
    result = number * multiplier

    if negative or result < 0:
        raise ValueError("Size must be non-negative")

    return int(result)


def _parse_duration_value(
    value: str | int | float | None, *, allow_keywords: bool
) -> float | None:
    """Parse duration string to seconds."""
    if value is None:
        return None

    if isinstance(value, (int, float)):
        if value < 0:
            raise ValueError("Duration must be non-negative")
        return float(value)

    raw_value = str(value).strip()
    value_str = _strip_quotes(raw_value)
    negative = value_str.startswith("-")
    if negative:
        value_str = value_str[1:].strip()

    if re.fullmatch(r"\d+(?:\.\d+)?", value_str):
        if negative:
            raise ValueError("Duration must be non-negative")
        return float(value_str)

    if allow_keywords:
        normalized = value_str.lower()
        if normalized in ROTATION_INTERVALS:
            if negative:
                raise ValueError("Duration must be non-negative")
            return float(ROTATION_INTERVALS[normalized])

    match = DURATION_PATTERN.match(value_str)
    if not match:
        keyword_hint = " or 'hourly', 'daily', 'weekly'" if allow_keywords else ""
        raise ValueError(
            f"Invalid duration format: '{raw_value}'. "
            f"Valid formats: '30s', '5m', '1h', '7d', '2w', '100ms', '0.5s', "
            f"or numeric seconds (e.g., 0.1){keyword_hint}"
        )

    number_str, unit_str = match.groups()
    number = float(number_str)
    multiplier = DURATION_UNITS[unit_str.lower()]
    result = number * multiplier

    if negative or result < 0:
        raise ValueError("Duration must be non-negative")

    return float(result)


def _parse_duration(value: str | int | float | None) -> float | None:
    return _parse_duration_value(value, allow_keywords=False)


def _parse_rotation_duration(value: str | int | float | None) -> float | None:
    return _parse_duration_value(value, allow_keywords=True)


SizeField = Annotated[int, BeforeValidator(_parse_size)]
DurationField = Annotated[float, BeforeValidator(_parse_duration)]
OptionalSizeField = Annotated[int | None, BeforeValidator(_parse_size)]
OptionalDurationField = Annotated[float | None, BeforeValidator(_parse_duration)]
RotationDurationField = Annotated[float, BeforeValidator(_parse_rotation_duration)]
OptionalRotationDurationField = Annotated[
    float | None, BeforeValidator(_parse_rotation_duration)
]

__all__ = [
    "SizeField",
    "DurationField",
    "OptionalSizeField",
    "OptionalDurationField",
    "RotationDurationField",
    "OptionalRotationDurationField",
]
