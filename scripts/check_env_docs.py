#!/usr/bin/env python3
"""Validate environment variable documentation consistency.

This script ensures the manual env vars doc (docs/user-guide/environment-variables.md)
stays in sync with the auto-generated reference (docs/env-vars.md).

Checks performed:
1. Every env var in the manual doc must be valid (exist in auto-generated OR be a known short alias)
2. Required env vars (core settings, sinks) must be covered by the manual doc
3. Optional env vars (advanced/internal) are reported but don't cause failure

Exit codes:
- 0: All checks pass
- 1: Invalid env vars found in manual doc (vars that don't exist)
- 2: File not found or parse error
- 3: Manual doc is missing required env vars
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Short alias mappings: short form -> full canonical form
# These are defined by @model_validator methods in settings.py
SHORT_ALIAS_MAPPINGS: dict[str, str] = {
    # CloudWatch aliases (_apply_cloudwatch_env_aliases)
    "FAPILOG_CLOUDWATCH__LOG_GROUP_NAME": "FAPILOG_SINK_CONFIG__CLOUDWATCH__LOG_GROUP_NAME",
    "FAPILOG_CLOUDWATCH__LOG_STREAM_NAME": "FAPILOG_SINK_CONFIG__CLOUDWATCH__LOG_STREAM_NAME",
    "FAPILOG_CLOUDWATCH__REGION": "FAPILOG_SINK_CONFIG__CLOUDWATCH__REGION",
    "FAPILOG_CLOUDWATCH__ENDPOINT_URL": "FAPILOG_SINK_CONFIG__CLOUDWATCH__ENDPOINT_URL",
    "FAPILOG_CLOUDWATCH__BATCH_SIZE": "FAPILOG_SINK_CONFIG__CLOUDWATCH__BATCH_SIZE",
    "FAPILOG_CLOUDWATCH__BATCH_TIMEOUT_SECONDS": "FAPILOG_SINK_CONFIG__CLOUDWATCH__BATCH_TIMEOUT_SECONDS",
    "FAPILOG_CLOUDWATCH__CREATE_LOG_GROUP": "FAPILOG_SINK_CONFIG__CLOUDWATCH__CREATE_LOG_GROUP",
    "FAPILOG_CLOUDWATCH__CREATE_LOG_STREAM": "FAPILOG_SINK_CONFIG__CLOUDWATCH__CREATE_LOG_STREAM",
    "FAPILOG_CLOUDWATCH__MAX_RETRIES": "FAPILOG_SINK_CONFIG__CLOUDWATCH__MAX_RETRIES",
    "FAPILOG_CLOUDWATCH__RETRY_BASE_DELAY": "FAPILOG_SINK_CONFIG__CLOUDWATCH__RETRY_BASE_DELAY",
    "FAPILOG_CLOUDWATCH__CIRCUIT_BREAKER_ENABLED": "FAPILOG_SINK_CONFIG__CLOUDWATCH__CIRCUIT_BREAKER_ENABLED",
    "FAPILOG_CLOUDWATCH__CIRCUIT_BREAKER_THRESHOLD": "FAPILOG_SINK_CONFIG__CLOUDWATCH__CIRCUIT_BREAKER_THRESHOLD",
    # Loki aliases (_apply_loki_env_aliases)
    "FAPILOG_LOKI__URL": "FAPILOG_SINK_CONFIG__LOKI__URL",
    "FAPILOG_LOKI__TENANT_ID": "FAPILOG_SINK_CONFIG__LOKI__TENANT_ID",
    "FAPILOG_LOKI__LABELS": "FAPILOG_SINK_CONFIG__LOKI__LABELS",
    "FAPILOG_LOKI__LABEL_KEYS": "FAPILOG_SINK_CONFIG__LOKI__LABEL_KEYS",
    "FAPILOG_LOKI__BATCH_SIZE": "FAPILOG_SINK_CONFIG__LOKI__BATCH_SIZE",
    "FAPILOG_LOKI__BATCH_TIMEOUT_SECONDS": "FAPILOG_SINK_CONFIG__LOKI__BATCH_TIMEOUT_SECONDS",
    "FAPILOG_LOKI__TIMEOUT_SECONDS": "FAPILOG_SINK_CONFIG__LOKI__TIMEOUT_SECONDS",
    "FAPILOG_LOKI__MAX_RETRIES": "FAPILOG_SINK_CONFIG__LOKI__MAX_RETRIES",
    "FAPILOG_LOKI__RETRY_BASE_DELAY": "FAPILOG_SINK_CONFIG__LOKI__RETRY_BASE_DELAY",
    "FAPILOG_LOKI__CIRCUIT_BREAKER_ENABLED": "FAPILOG_SINK_CONFIG__LOKI__CIRCUIT_BREAKER_ENABLED",
    "FAPILOG_LOKI__CIRCUIT_BREAKER_THRESHOLD": "FAPILOG_SINK_CONFIG__LOKI__CIRCUIT_BREAKER_THRESHOLD",
    "FAPILOG_LOKI__AUTH_USERNAME": "FAPILOG_SINK_CONFIG__LOKI__AUTH_USERNAME",
    "FAPILOG_LOKI__AUTH_PASSWORD": "FAPILOG_SINK_CONFIG__LOKI__AUTH_PASSWORD",
    "FAPILOG_LOKI__AUTH_TOKEN": "FAPILOG_SINK_CONFIG__LOKI__AUTH_TOKEN",
    # Postgres aliases (_apply_postgres_env_aliases)
    "FAPILOG_POSTGRES__DSN": "FAPILOG_SINK_CONFIG__POSTGRES__DSN",
    "FAPILOG_POSTGRES__HOST": "FAPILOG_SINK_CONFIG__POSTGRES__HOST",
    "FAPILOG_POSTGRES__PORT": "FAPILOG_SINK_CONFIG__POSTGRES__PORT",
    "FAPILOG_POSTGRES__DATABASE": "FAPILOG_SINK_CONFIG__POSTGRES__DATABASE",
    "FAPILOG_POSTGRES__USER": "FAPILOG_SINK_CONFIG__POSTGRES__USER",
    "FAPILOG_POSTGRES__PASSWORD": "FAPILOG_SINK_CONFIG__POSTGRES__PASSWORD",
    "FAPILOG_POSTGRES__TABLE_NAME": "FAPILOG_SINK_CONFIG__POSTGRES__TABLE_NAME",
    "FAPILOG_POSTGRES__SCHEMA_NAME": "FAPILOG_SINK_CONFIG__POSTGRES__SCHEMA_NAME",
    "FAPILOG_POSTGRES__CREATE_TABLE": "FAPILOG_SINK_CONFIG__POSTGRES__CREATE_TABLE",
    "FAPILOG_POSTGRES__USE_JSONB": "FAPILOG_SINK_CONFIG__POSTGRES__USE_JSONB",
    "FAPILOG_POSTGRES__INCLUDE_RAW_JSON": "FAPILOG_SINK_CONFIG__POSTGRES__INCLUDE_RAW_JSON",
    "FAPILOG_POSTGRES__MIN_POOL_SIZE": "FAPILOG_SINK_CONFIG__POSTGRES__MIN_POOL_SIZE",
    "FAPILOG_POSTGRES__MAX_POOL_SIZE": "FAPILOG_SINK_CONFIG__POSTGRES__MAX_POOL_SIZE",
    "FAPILOG_POSTGRES__POOL_ACQUIRE_TIMEOUT": "FAPILOG_SINK_CONFIG__POSTGRES__POOL_ACQUIRE_TIMEOUT",
    "FAPILOG_POSTGRES__BATCH_SIZE": "FAPILOG_SINK_CONFIG__POSTGRES__BATCH_SIZE",
    "FAPILOG_POSTGRES__BATCH_TIMEOUT_SECONDS": "FAPILOG_SINK_CONFIG__POSTGRES__BATCH_TIMEOUT_SECONDS",
    "FAPILOG_POSTGRES__MAX_RETRIES": "FAPILOG_SINK_CONFIG__POSTGRES__MAX_RETRIES",
    "FAPILOG_POSTGRES__RETRY_BASE_DELAY": "FAPILOG_SINK_CONFIG__POSTGRES__RETRY_BASE_DELAY",
    "FAPILOG_POSTGRES__CIRCUIT_BREAKER_ENABLED": "FAPILOG_SINK_CONFIG__POSTGRES__CIRCUIT_BREAKER_ENABLED",
    "FAPILOG_POSTGRES__CIRCUIT_BREAKER_THRESHOLD": "FAPILOG_SINK_CONFIG__POSTGRES__CIRCUIT_BREAKER_THRESHOLD",
    "FAPILOG_POSTGRES__EXTRACT_FIELDS": "FAPILOG_SINK_CONFIG__POSTGRES__EXTRACT_FIELDS",
    # Size Guard aliases (_apply_size_guard_env_aliases)
    "FAPILOG_SIZE_GUARD__ACTION": "FAPILOG_PROCESSOR_CONFIG__SIZE_GUARD__ACTION",
    "FAPILOG_SIZE_GUARD__MAX_BYTES": "FAPILOG_PROCESSOR_CONFIG__SIZE_GUARD__MAX_BYTES",
    "FAPILOG_SIZE_GUARD__PRESERVE_FIELDS": "FAPILOG_PROCESSOR_CONFIG__SIZE_GUARD__PRESERVE_FIELDS",
    # Sink Routing aliases (_apply_sink_routing_env_aliases)
    "FAPILOG_SINK_ROUTING__ENABLED": "FAPILOG_SINK_ROUTING__ENABLED",  # top-level, same
    "FAPILOG_SINK_ROUTING__OVERLAP": "FAPILOG_SINK_ROUTING__OVERLAP",
    "FAPILOG_SINK_ROUTING__RULES": "FAPILOG_SINK_ROUTING__RULES",
    "FAPILOG_SINK_ROUTING__FALLBACK_SINKS": "FAPILOG_SINK_ROUTING__FALLBACK_SINKS",
    # File sink (special: defined in __init__.py, not settings.py)
    "FAPILOG_FILE__DIRECTORY": "__SPECIAL_FILE_SINK__",
    "FAPILOG_FILE__FILENAME_PREFIX": "__SPECIAL_FILE_SINK__",
    "FAPILOG_FILE__MODE": "__SPECIAL_FILE_SINK__",
    "FAPILOG_FILE__MAX_BYTES": "__SPECIAL_FILE_SINK__",
    "FAPILOG_FILE__INTERVAL_SECONDS": "__SPECIAL_FILE_SINK__",
    "FAPILOG_FILE__MAX_FILES": "__SPECIAL_FILE_SINK__",
    "FAPILOG_FILE__MAX_TOTAL_BYTES": "__SPECIAL_FILE_SINK__",
    "FAPILOG_FILE__COMPRESS_ROTATED": "__SPECIAL_FILE_SINK__",
    # Runtime info enricher (special: reads from env directly in enricher)
    "FAPILOG_SERVICE": "__SPECIAL_ENRICHER__",
    "FAPILOG_ENV": "__SPECIAL_ENRICHER__",
    "FAPILOG_VERSION": "__SPECIAL_ENRICHER__",
}

# Reverse mapping for quick lookup
CANONICAL_TO_SHORT = {
    v: k for k, v in SHORT_ALIAS_MAPPINGS.items() if not v.startswith("__")
}

# Required env vars - these specific vars MUST be documented (CI fails if missing)
# Using specific var names for CORE since not all CORE settings are user-facing
REQUIRED_VARS = {
    # Core settings users commonly configure
    "FAPILOG_CORE__LOG_LEVEL",
    "FAPILOG_CORE__MAX_QUEUE_SIZE",
    "FAPILOG_CORE__BATCH_MAX_SIZE",
    "FAPILOG_CORE__BATCH_TIMEOUT_SECONDS",
    "FAPILOG_CORE__BACKPRESSURE_WAIT_MS",
    "FAPILOG_CORE__DROP_ON_FULL",
    "FAPILOG_CORE__SINKS",
    "FAPILOG_CORE__FILTERS",
    "FAPILOG_CORE__ENABLE_METRICS",
    "FAPILOG_CORE__ERROR_DEDUPE_WINDOW_SECONDS",
    "FAPILOG_CORE__SINK_CIRCUIT_BREAKER_ENABLED",
    "FAPILOG_CORE__SINK_PARALLEL_WRITES",
    # HTTP sink (top-level)
    "FAPILOG_HTTP__ENDPOINT",
    "FAPILOG_HTTP__TIMEOUT_SECONDS",
    "FAPILOG_HTTP__RETRY_MAX_ATTEMPTS",
    "FAPILOG_HTTP__RETRY_BACKOFF_SECONDS",
    "FAPILOG_HTTP__BATCH_SIZE",
    "FAPILOG_HTTP__BATCH_TIMEOUT_SECONDS",
    "FAPILOG_HTTP__BATCH_FORMAT",
    "FAPILOG_HTTP__BATCH_WRAPPER_KEY",
    "FAPILOG_HTTP__HEADERS_JSON",
}

# Required prefixes - all vars with these prefixes MUST be documented
REQUIRED_PREFIXES = (
    "FAPILOG_SINK_CONFIG__CLOUDWATCH__",
    "FAPILOG_SINK_CONFIG__LOKI__",
    "FAPILOG_SINK_CONFIG__POSTGRES__",
    "FAPILOG_SINK_CONFIG__WEBHOOK__",
    "FAPILOG_SINK_CONFIG__AUDIT__",
    "FAPILOG_SINK_ROUTING__",
    "FAPILOG_PROCESSOR_CONFIG__SIZE_GUARD__",
)

# Optional prefixes - informational only, no CI failure
OPTIONAL_PREFIXES = (
    "FAPILOG_CORE__",  # Non-required CORE settings are optional
    "FAPILOG_HTTP__",  # Non-required HTTP settings are optional
    "FAPILOG_SECURITY__",  # Advanced security settings
    "FAPILOG_OBSERVABILITY__",  # Internal observability config
    "FAPILOG_PLUGINS__",  # Plugin system internals
    "FAPILOG_ENRICHER_CONFIG__",  # Enricher config (advanced)
    "FAPILOG_FILTER_CONFIG__",  # Filter config (advanced)
    "FAPILOG_REDACTOR_CONFIG__",  # Redactor config (advanced)
    "FAPILOG_PROCESSOR_CONFIG__EXTRA",  # Extra processors
    "FAPILOG_PROCESSOR_CONFIG__ZERO_COPY",  # Internal processor
    "FAPILOG_SINK_CONFIG__SEALED__",  # Tamper-evident (enterprise)
    "FAPILOG_SINK_CONFIG__EXTRA",  # Third-party sinks
    "FAPILOG_SINK_CONFIG__STDOUT_JSON",  # No config needed
    "FAPILOG_SINK_CONFIG__HTTP__",  # Covered by top-level FAPILOG_HTTP__
    "FAPILOG_SINK_CONFIG__ROTATING_FILE__",  # Covered by FAPILOG_FILE__ aliases
    "FAPILOG_SCHEMA_VERSION",  # Internal versioning
)


def extract_env_vars(markdown_content: str) -> set[str]:
    """Extract all FAPILOG_* env var names from markdown content."""
    # Match backtick-wrapped env vars like `FAPILOG_CORE__LOG_LEVEL`
    # Must have at least one component after FAPILOG_ (letters/numbers/underscores)
    pattern = r"`(FAPILOG_[A-Z][A-Z0-9_]*(?:__[A-Z0-9_]+)*)`"
    matches = re.findall(pattern, markdown_content)
    # Also match ENV (used in runtime_info section)
    if "`ENV`" in markdown_content:
        matches.append("ENV")
    return set(matches)


def normalize_to_canonical(env_var: str) -> str:
    """Convert a short alias to its canonical form, or return as-is."""
    return SHORT_ALIAS_MAPPINGS.get(env_var, env_var)


def main() -> int:
    repo_root = Path(__file__).parent.parent
    auto_generated = repo_root / "docs" / "env-vars.md"
    manual_doc = repo_root / "docs" / "user-guide" / "environment-variables.md"

    # Check files exist
    if not auto_generated.exists():
        print(f"ERROR: Auto-generated doc not found: {auto_generated}")
        print("Run: python scripts/generate_env_matrix.py")
        return 2

    if not manual_doc.exists():
        print(f"ERROR: Manual doc not found: {manual_doc}")
        return 2

    # Parse both files
    auto_vars = extract_env_vars(auto_generated.read_text(encoding="utf-8"))
    manual_vars = extract_env_vars(manual_doc.read_text(encoding="utf-8"))

    print(f"Auto-generated doc: {len(auto_vars)} env vars")
    print(f"Manual doc: {len(manual_vars)} env vars")
    print()

    # Check 1: Every env var in manual doc must be valid
    invalid_vars: list[str] = []
    for var in sorted(manual_vars):
        if var == "ENV":  # Special case: ENV fallback for FAPILOG_ENV
            continue
        canonical = normalize_to_canonical(var)
        if canonical.startswith("__SPECIAL"):
            # Known special vars (file sink, enricher env)
            continue
        if canonical not in auto_vars and var not in auto_vars:
            invalid_vars.append(var)

    if invalid_vars:
        print("ERROR: Manual doc contains env vars that don't exist:")
        for var in invalid_vars:
            print(f"  - {var}")
        print()
        print("These may be typos or the Settings model has changed.")
        return 1

    # Check 2: Categorize undocumented env vars as required or optional
    documented_canonical: set[str] = set()
    for var in manual_vars:
        documented_canonical.add(normalize_to_canonical(var))
        documented_canonical.add(var)  # Also add the original

    undocumented = auto_vars - documented_canonical
    # Filter out vars that have a short alias documented
    truly_undocumented: list[str] = []
    for var in sorted(undocumented):
        short = CANONICAL_TO_SHORT.get(var)
        if short and short in manual_vars:
            continue  # Short alias is documented
        truly_undocumented.append(var)

    # Separate into required and optional
    missing_required: list[str] = []
    missing_optional: list[str] = []

    for var in truly_undocumented:
        # Check if this specific var is required
        is_required_var = var in REQUIRED_VARS
        # Check if var matches a required prefix
        is_required_prefix = any(var.startswith(prefix) for prefix in REQUIRED_PREFIXES)
        # Check if var matches an optional prefix
        is_optional = any(var.startswith(prefix) for prefix in OPTIONAL_PREFIXES)

        if is_required_var or (is_required_prefix and not is_optional):
            missing_required.append(var)
        else:
            missing_optional.append(var)

    # Report optional (informational)
    if missing_optional:
        print(f"INFO: {len(missing_optional)} optional env vars not in manual doc:")
        by_prefix: dict[str, list[str]] = {}
        for var in missing_optional:
            parts = var.split("__")
            prefix = "__".join(parts[:2]) if len(parts) > 1 else parts[0]
            by_prefix.setdefault(prefix, []).append(var)
        for prefix in sorted(by_prefix.keys()):
            print(f"  {prefix}: {len(by_prefix[prefix])} vars")
        print()

    # Fail on missing required
    if missing_required:
        print(
            f"ERROR: {len(missing_required)} required env vars missing from manual doc:"
        )
        by_prefix = {}
        for var in missing_required:
            parts = var.split("__")
            prefix = "__".join(parts[:2]) if len(parts) > 1 else parts[0]
            by_prefix.setdefault(prefix, []).append(var)

        for prefix in sorted(by_prefix.keys()):
            print(f"  {prefix}:")
            for var in by_prefix[prefix]:
                print(f"    - {var}")
        print()
        print("Add these to docs/user-guide/environment-variables.md")
        return 3

    print("✓ All env vars in manual doc are valid")
    print("✓ All required env vars are documented")
    return 0


if __name__ == "__main__":
    sys.exit(main())
