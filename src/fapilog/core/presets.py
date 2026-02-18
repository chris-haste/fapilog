"""Built-in configuration presets for common use cases."""

from __future__ import annotations

import copy
import warnings
from typing import Any, Literal

PresetName = Literal[
    "adaptive",
    "dev",
    "hardened",
    "minimal",
    "production",
    "serverless",
]

PRESETS: dict[str, dict[str, Any]] = {
    "dev": {
        "core": {
            "log_level": "DEBUG",
            "internal_logging_enabled": True,
            "batch_max_size": 1,
            "sinks": ["stdout_pretty"],
            "enrichers": ["runtime_info", "context_vars"],
            "redactors": [],  # Explicit opt-out for development visibility
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
            "worker_count": 2,
            "batch_max_size": 256,
            "max_queue_size": 10000,
            "sink_concurrency": 8,
            "shutdown_timeout_seconds": 25.0,
            "batch_timeout_seconds": 0.25,
            "drop_on_full": False,
            "redaction_fail_mode": "warn",
            "sinks": ["stdout_json"],
            "enrichers": ["runtime_info", "context_vars"],
            "redactors": ["field_mask", "regex_mask", "url_credentials"],
            "protected_levels": ["ERROR", "CRITICAL"],
            "sink_circuit_breaker_enabled": True,
            "sink_circuit_breaker_fallback_sink": "rotating_file",
        },
        "adaptive": {
            "enabled": True,
            "max_workers": 4,
            "max_queue_growth": 3.0,
            "batch_sizing": False,
            "circuit_pressure_boost": 0.25,
            "cooldown_seconds": 1.0,
            "check_interval_seconds": 0.25,
        },
        "sink_config": {
            "rotating_file": {
                "directory": "./logs",
                "filename_prefix": "fapilog",
                "max_bytes": 52_428_800,
                "max_files": 10,
                "compress_rotated": True,
            },
            "postgres": {
                "create_table": False,
            },
        },
        "enricher_config": {
            "runtime_info": {},
            "context_vars": {},
        },
        "redactor_config": {
            "field_mask": {},
            "regex_mask": {},
            "url_credentials": {},
        },
        "_apply_credentials_preset": True,
    },
    "minimal": {
        "core": {
            "redactors": [],  # Explicit opt-out for minimal overhead
        },
    },
    "serverless": {
        "core": {
            "log_level": "INFO",
            "worker_count": 2,  # 30x throughput improvement over default (Story 10.44)
            "batch_max_size": 25,  # Smaller batches for short-lived functions
            "drop_on_full": True,  # Don't block in time-constrained environments
            "redaction_fail_mode": "warn",
            "sinks": ["stdout_json"],  # Stdout only, captured by cloud provider
            "enrichers": ["runtime_info", "context_vars"],
            "redactors": ["field_mask", "regex_mask", "url_credentials"],
        },
        "enricher_config": {
            "runtime_info": {},
            "context_vars": {},
        },
        "redactor_config": {
            # Minimal config - CREDENTIALS preset applied automatically
            # via with_preset("serverless") -> with_redaction(preset="CREDENTIALS")
            "field_mask": {},
            "regex_mask": {},
            "url_credentials": {},
        },
        "_apply_credentials_preset": True,
    },
    "hardened": {
        "core": {
            "log_level": "INFO",
            "worker_count": 2,  # 30x throughput improvement over default (Story 10.44)
            "batch_max_size": 100,
            "drop_on_full": False,  # Never lose logs
            "redaction_fail_mode": "closed",  # Drop event if redaction fails
            "strict_envelope_mode": True,  # Reject malformed envelopes
            "fallback_redact_mode": "inherit",  # Full redaction on fallback
            "fallback_scrub_raw": True,  # Scrub raw output
            "sinks": ["stdout_json", "rotating_file"],
            "enrichers": ["runtime_info", "context_vars"],
            "redactors": [
                "field_mask",
                "regex_mask",
                "url_credentials",
                "field_blocker",
            ],
        },
        "sink_config": {
            "rotating_file": {
                "directory": "./logs",
                "filename_prefix": "fapilog",
                "max_bytes": 52_428_800,  # 50 MB
                "max_files": 10,
                "compress_rotated": True,
            },
            "postgres": {
                "create_table": False,  # Require explicit provisioning
            },
        },
        "enricher_config": {
            "runtime_info": {},
            "context_vars": {},
        },
        "redactor_config": {
            "field_mask": {},
            "regex_mask": {},
            "url_credentials": {},
            "field_blocker": {},
        },
        # Marker for automatic CREDENTIALS preset application
        "_apply_credentials_preset": True,
        # Additional presets for hardened mode (HIPAA + PCI-DSS)
        "_apply_redaction_presets": ["HIPAA_PHI", "PCI_DSS"],
    },
}


# Deprecated aliases that resolve to another preset
_DEPRECATED_ALIASES: dict[str, str] = {
    "adaptive": "production",
}


def validate_preset(name: PresetName) -> None:
    """Validate preset name.

    Args:
        name: Preset name to validate

    Raises:
        ValueError: If preset name is invalid
    """
    if name not in PRESETS and name not in _DEPRECATED_ALIASES:
        valid = ", ".join(sorted(set(PRESETS.keys()) | set(_DEPRECATED_ALIASES.keys())))
        raise ValueError(f"Invalid preset '{name}'. Valid presets: {valid}")


def get_preset(name: PresetName) -> dict[str, Any]:
    """Get preset configuration by name.

    Args:
        name: Preset name (dev, production, adaptive, minimal, serverless, hardened)

    Returns:
        Settings-compatible configuration dict (deep copy)

    Raises:
        ValueError: If preset name is invalid
    """
    validate_preset(name)
    if name in _DEPRECATED_ALIASES:
        target = _DEPRECATED_ALIASES[name]
        warnings.warn(
            f"The '{name}' preset is deprecated. "
            f"Use '{target}' instead — it now includes all adaptive features.",
            DeprecationWarning,
            stacklevel=2,
        )
        return copy.deepcopy(PRESETS[target])
    return copy.deepcopy(PRESETS[name])


def list_presets() -> list[str]:
    """Return sorted list of available preset names (includes deprecated aliases)."""
    return sorted(set(PRESETS.keys()) | set(_DEPRECATED_ALIASES.keys()))
