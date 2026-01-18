"""Built-in configuration presets for common use cases."""

from __future__ import annotations

import copy
from typing import Any

PRESETS: dict[str, dict[str, Any]] = {
    "dev": {
        "core": {
            "log_level": "DEBUG",
            "internal_logging_enabled": True,
            "batch_max_size": 1,
            "sinks": ["stdout_pretty"],
            "enrichers": ["runtime_info", "context_vars"],
        },
        "enricher_config": {
            "runtime_info": {},
            "context_vars": {},
        },
        "redactor_config": {
            "field_mask": {"fields_to_mask": []},
        },
    },
    "production": {
        "core": {
            "log_level": "INFO",
            "batch_max_size": 100,
            "drop_on_full": False,
            "sinks": ["stdout_json", "rotating_file"],
            "enrichers": ["runtime_info", "context_vars"],
            "redactors": ["field_mask", "regex_mask", "url_credentials"],
        },
        "sink_config": {
            "rotating_file": {
                "directory": "./logs",
                "filename_prefix": "fapilog",
                "max_bytes": 52_428_800,
                "max_files": 10,
                "compress_rotated": True,
            }
        },
        "enricher_config": {
            "runtime_info": {},
            "context_vars": {},
        },
        "redactor_config": {
            "field_mask": {
                "fields_to_mask": [
                    "metadata.password",
                    "metadata.api_key",
                    "metadata.token",
                    "metadata.secret",
                    "metadata.authorization",
                    "metadata.api_secret",
                    "metadata.private_key",
                    "metadata.ssn",
                    "metadata.credit_card",
                ],
            },
            "regex_mask": {
                "patterns": [
                    r"(?i).*password.*",
                    r"(?i).*passwd.*",
                    r"(?i).*api[_-]?key.*",
                    r"(?i).*apikey.*",
                    r"(?i).*secret.*",
                    r"(?i).*token.*",
                    r"(?i).*authorization.*",
                    r"(?i).*private[_-]?key.*",
                    r"(?i).*ssn.*",
                    r"(?i).*credit[_-]?card.*",
                ],
            },
            "url_credentials": {},
        },
    },
    "fastapi": {
        "core": {
            "log_level": "INFO",
            "batch_max_size": 50,
            "sinks": ["stdout_json"],
            "enrichers": ["context_vars"],
        },
        "enricher_config": {
            "context_vars": {},
        },
    },
    "minimal": {},
}


def validate_preset(name: str) -> None:
    """Validate preset name.

    Args:
        name: Preset name to validate

    Raises:
        ValueError: If preset name is invalid
    """
    if name not in PRESETS:
        valid = ", ".join(sorted(PRESETS.keys()))
        raise ValueError(f"Invalid preset '{name}'. Valid presets: {valid}")


def get_preset(name: str) -> dict[str, Any]:
    """Get preset configuration by name.

    Args:
        name: Preset name (dev, production, fastapi, minimal)

    Returns:
        Settings-compatible configuration dict (deep copy)

    Raises:
        ValueError: If preset name is invalid
    """
    validate_preset(name)
    return copy.deepcopy(PRESETS[name])


def list_presets() -> list[str]:
    """Return sorted list of available preset names."""
    return sorted(PRESETS.keys())
