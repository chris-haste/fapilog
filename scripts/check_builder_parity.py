#!/usr/bin/env python3
"""Check builder API parity with Settings - ALL categories.

This script ensures all Settings fields have corresponding builder methods.
Run as a pre-commit hook or manually via: python scripts/check_builder_parity.py

Checks:
1. CoreSettings fields -> with_*() methods
2. Sink settings -> add_*() method parameters
3. Filter/Processor settings -> with_*() methods
4. Advanced settings -> routing/redactor/plugin methods
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def get_model_fields(model_class: type[Any]) -> set[str]:
    """Extract field names from a Pydantic model.

    Args:
        model_class: A Pydantic model class

    Returns:
        Set of field names, excluding model_config
    """
    return set(model_class.model_fields.keys()) - {"model_config"}


def check_core_settings() -> list[str]:
    """Check CoreSettings parity.

    Returns:
        List of error messages, empty if all fields covered
    """
    from fapilog.core.settings import CoreSettings
    from scripts.builder_param_mappings import CORE_COVERAGE, CORE_EXCLUSIONS

    fields = get_model_fields(CoreSettings) - CORE_EXCLUSIONS
    covered: set[str] = set()
    for method_fields in CORE_COVERAGE.values():
        covered.update(method_fields)

    missing = fields - covered
    if missing:
        return [f"CoreSettings fields without builder methods: {sorted(missing)}"]
    return []


def check_sink_settings() -> list[str]:
    """Check sink settings parity (CloudWatch, Loki, Postgres).

    Returns:
        List of error messages, empty if all fields covered
    """
    from fapilog.core.settings import (
        CloudWatchSinkSettings,
        LokiSinkSettings,
        PostgresSinkSettings,
    )
    from scripts.builder_param_mappings import SINK_EXCLUSIONS, SINK_PARAM_MAPPINGS

    errors: list[str] = []
    sink_checks = [
        ("add_cloudwatch", CloudWatchSinkSettings),
        ("add_loki", LokiSinkSettings),
        ("add_postgres", PostgresSinkSettings),
    ]

    for method_name, settings_class in sink_checks:
        fields = get_model_fields(settings_class) - SINK_EXCLUSIONS
        if method_name not in SINK_PARAM_MAPPINGS:
            errors.append(f"Missing SINK_PARAM_MAPPINGS for {method_name}")
            continue

        covered = set(SINK_PARAM_MAPPINGS[method_name].values())
        missing = fields - covered
        if missing:
            errors.append(
                f"{settings_class.__name__} fields without {method_name}() coverage: "
                f"{sorted(missing)}"
            )

    return errors


def check_filter_settings() -> list[str]:
    """Check filter builder method coverage.

    Returns:
        List of error messages, empty if all filters covered
    """
    from scripts.builder_param_mappings import FILTER_COVERAGE

    # FilterConfig uses dict[str, Any] for each filter, so we check
    # that each filter type has a with_*() method
    expected_filters = {
        "sampling",
        "rate_limit",
        "adaptive_sampling",
        "trace_sampling",
        "first_occurrence",
    }
    covered = set(FILTER_COVERAGE.keys())
    missing = expected_filters - covered

    if missing:
        return [f"FilterConfig types without builder methods: {sorted(missing)}"]
    return []


def check_processor_settings() -> list[str]:
    """Check processor builder method coverage.

    Returns:
        List of error messages, empty if all processors covered
    """
    from fapilog.core.settings import SizeGuardSettings
    from scripts.builder_param_mappings import PROCESSOR_COVERAGE

    errors: list[str] = []
    if "size_guard" not in PROCESSOR_COVERAGE:
        errors.append("Missing PROCESSOR_COVERAGE for size_guard")
    else:
        fields = get_model_fields(SizeGuardSettings)
        covered = set(PROCESSOR_COVERAGE["size_guard"].values())
        missing = fields - covered
        if missing:
            errors.append(
                f"SizeGuardSettings fields without with_size_guard() coverage: "
                f"{sorted(missing)}"
            )

    return errors


def check_advanced_settings() -> list[str]:
    """Check advanced settings (routing, redactors, plugins).

    Returns:
        List of error messages, empty if all advanced settings covered
    """
    from fapilog.core.settings import (
        RedactorFieldMaskSettings,
        RedactorRegexMaskSettings,
        RedactorUrlCredentialsSettings,
        SinkRoutingSettings,
    )
    from scripts.builder_param_mappings import ADVANCED_COVERAGE

    errors: list[str] = []

    # Routing settings check
    if "with_routing" not in ADVANCED_COVERAGE:
        errors.append("Missing ADVANCED_COVERAGE for with_routing")
    else:
        # Routing has 'enabled' field that's implicit (routing is enabled by calling the method)
        fields = get_model_fields(SinkRoutingSettings) - {"enabled"}
        covered = set(ADVANCED_COVERAGE["with_routing"].values())
        missing = fields - covered
        if missing:
            errors.append(
                f"SinkRoutingSettings fields without with_routing() coverage: "
                f"{sorted(missing)}"
            )

    # Field mask redactor
    if "with_field_mask" not in ADVANCED_COVERAGE:
        errors.append("Missing ADVANCED_COVERAGE for with_field_mask")
    else:
        fields = get_model_fields(RedactorFieldMaskSettings)
        covered = set(ADVANCED_COVERAGE["with_field_mask"].values())
        missing = fields - covered
        if missing:
            errors.append(
                f"RedactorFieldMaskSettings fields without with_field_mask() coverage: "
                f"{sorted(missing)}"
            )

    # Regex mask redactor
    if "with_regex_mask" not in ADVANCED_COVERAGE:
        errors.append("Missing ADVANCED_COVERAGE for with_regex_mask")
    else:
        fields = get_model_fields(RedactorRegexMaskSettings)
        covered = set(ADVANCED_COVERAGE["with_regex_mask"].values())
        missing = fields - covered
        if missing:
            errors.append(
                f"RedactorRegexMaskSettings fields without with_regex_mask() coverage: "
                f"{sorted(missing)}"
            )

    # URL credentials redactor
    if "with_url_credential_redaction" not in ADVANCED_COVERAGE:
        errors.append("Missing ADVANCED_COVERAGE for with_url_credential_redaction")
    else:
        fields = get_model_fields(RedactorUrlCredentialsSettings)
        covered = set(ADVANCED_COVERAGE["with_url_credential_redaction"].values())
        missing = fields - covered
        if missing:
            errors.append(
                f"RedactorUrlCredentialsSettings fields without coverage: "
                f"{sorted(missing)}"
            )

    # Plugins settings - these are nested in Settings.PluginsSettings
    # We check this separately since it's a nested class
    from fapilog.core.settings import Settings

    if "with_plugins" not in ADVANCED_COVERAGE:
        errors.append("Missing ADVANCED_COVERAGE for with_plugins")
    else:
        fields = get_model_fields(Settings.PluginsSettings)
        covered = set(ADVANCED_COVERAGE["with_plugins"].values())
        missing = fields - covered
        if missing:
            errors.append(
                f"PluginsSettings fields without with_plugins() coverage: "
                f"{sorted(missing)}"
            )

    return errors


def _setup_paths() -> None:
    """Set up import paths for both script and module execution."""
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent

    # Add src/ to path for fapilog imports
    src_path = project_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    # Add project root to path for scripts imports
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


def main() -> int:
    """Run all parity checks.

    Returns:
        0 if all checks pass, 1 if any check fails
    """
    _setup_paths()

    all_errors: list[str] = []
    all_errors.extend(check_core_settings())
    all_errors.extend(check_sink_settings())
    all_errors.extend(check_filter_settings())
    all_errors.extend(check_processor_settings())
    all_errors.extend(check_advanced_settings())

    if all_errors:
        print("Builder Parity Check Failed\n")
        for error in all_errors:
            print(f"  - {error}")
        print("\nEither:")
        print("1. Add builder method/parameter coverage")
        print("2. Add to appropriate exclusion list with rationale")
        print("\nSee: docs/contributing/configuration-parity.md")
        return 1

    print("Builder parity check passed (all categories)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
