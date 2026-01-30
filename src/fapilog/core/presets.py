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
            "worker_count": 2,  # 30x throughput improvement over default (Story 10.44)
            "batch_max_size": 100,
            "drop_on_full": False,
            "redaction_fail_mode": "warn",
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
            },
            "postgres": {
                "create_table": False,  # Require explicit table provisioning in production
            },
        },
        "enricher_config": {
            "runtime_info": {},
            "context_vars": {},
        },
        "redactor_config": {
            # Minimal config - CREDENTIALS preset applied automatically
            # via with_preset("production") -> with_redaction(preset="CREDENTIALS")
            "field_mask": {},
            "regex_mask": {},
            "url_credentials": {},
        },
        # Marker for automatic CREDENTIALS preset application
        "_apply_credentials_preset": True,
    },
    "production-latency": {
        "core": {
            "log_level": "INFO",
            "worker_count": 2,  # Multi-worker throughput
            "batch_max_size": 100,
            "drop_on_full": True,  # KEY DIFFERENCE: Accept drops for latency
            "redaction_fail_mode": "warn",
            "sinks": ["stdout_json"],  # No file sink for minimal I/O latency
            "enrichers": ["runtime_info", "context_vars"],
            "redactors": ["field_mask", "regex_mask", "url_credentials"],
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
    "fastapi": {
        "core": {
            "log_level": "INFO",
            "worker_count": 2,  # 30x throughput improvement over default (Story 10.44)
            "batch_max_size": 50,
            "redaction_fail_mode": "warn",
            "sinks": ["stdout_json"],
            "enrichers": ["context_vars"],
            "redactors": ["field_mask", "regex_mask", "url_credentials"],
        },
        "enricher_config": {
            "context_vars": {},
        },
        "redactor_config": {
            # Minimal config - CREDENTIALS preset applied automatically
            # via with_preset("fastapi") -> with_redaction(preset="CREDENTIALS")
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
            "redactors": ["field_mask", "regex_mask", "url_credentials"],
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
        },
        # Marker for automatic CREDENTIALS preset application
        "_apply_credentials_preset": True,
        # Additional presets for hardened mode (HIPAA + PCI-DSS)
        "_apply_redaction_presets": ["HIPAA_PHI", "PCI_DSS"],
    },
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
        name: Preset name (dev, production, fastapi, minimal, serverless)

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
