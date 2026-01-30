#!/usr/bin/env python
"""Validate builder filter/processor config keys match plugin config fields.

This script ensures that builder methods generate config dictionaries
with keys that are accepted by the corresponding plugin config classes
(which reject unknown fields via Pydantic model_config).

Story 12.28: Add Contract Tests and Parity Check for Filter/Processor Configs
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# Map filter/processor name -> (builder method name, plugin config class path)
FILTER_MAPPINGS: dict[str, tuple[str, str]] = {
    "sampling": (
        "with_sampling",
        "fapilog.plugins.filters.sampling:SamplingFilterConfig",
    ),
    "adaptive_sampling": (
        "with_adaptive_sampling",
        "fapilog.plugins.filters.adaptive_sampling:AdaptiveSamplingConfig",
    ),
    "trace_sampling": (
        "with_trace_sampling",
        "fapilog.plugins.filters.trace_sampling:TraceSamplingConfig",
    ),
    "rate_limit": (
        "with_rate_limit",
        "fapilog.plugins.filters.rate_limit:RateLimitFilterConfig",
    ),
    "first_occurrence": (
        "with_first_occurrence",
        "fapilog.plugins.filters.first_occurrence:FirstOccurrenceConfig",
    ),
}

PROCESSOR_MAPPINGS: dict[str, tuple[str, str]] = {
    "size_guard": (
        "with_size_guard",
        "fapilog.plugins.processors.size_guard:SizeGuardConfig",
    ),
}


def get_builder_ast() -> ast.Module:
    """Parse builder.py AST."""
    builder_path = Path(__file__).parent.parent / "src" / "fapilog" / "builder.py"
    return ast.parse(builder_path.read_text())


def extract_builder_config_keys(tree: ast.Module, method_name: str) -> set[str]:
    """Extract config keys set by a builder method from AST.

    Looks for patterns like:
        filter_config["filter_name"] = {"key1": ..., "key2": ...}
    or
        some_config: dict = {"key1": ..., "key2": ...}
        filter_config["filter_name"] = some_config
    """
    keys: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name != method_name:
            continue

        # Walk the function body looking for dict assignments
        for stmt in ast.walk(node):
            # Look for direct dict literal assignments to filter_config/processor_config
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    # filter_config["name"] = {...}
                    if isinstance(target, ast.Subscript) and isinstance(
                        stmt.value, ast.Dict
                    ):
                        for key in stmt.value.keys:
                            if isinstance(key, ast.Constant) and isinstance(
                                key.value, str
                            ):
                                keys.add(key.value)

    return keys


def extract_plugin_config_fields(config_class_path: str) -> set[str]:
    """Import config class and get field names."""
    module_path, class_name = config_class_path.rsplit(":", 1)

    import importlib

    module = importlib.import_module(module_path)
    config_class = getattr(module, class_name)

    # Get fields from Pydantic model or dataclass
    fields: set[str] = set()

    if hasattr(config_class, "model_fields"):
        # Pydantic v2
        fields = set(config_class.model_fields.keys())
    elif hasattr(config_class, "__dataclass_fields__"):
        # dataclass
        fields = set(config_class.__dataclass_fields__.keys())
    elif hasattr(config_class, "__fields__"):
        # Pydantic v1
        fields = set(config_class.__fields__.keys())

    return fields


def check_parity(
    name: str,
    method_name: str,
    config_path: str,
    tree: ast.Module,
) -> list[str]:
    """Check parity between builder and plugin config."""
    errors: list[str] = []

    builder_keys = extract_builder_config_keys(tree, method_name)
    plugin_fields = extract_plugin_config_fields(config_path)

    if not builder_keys:
        # Can't extract keys from AST - fall back to runtime check
        return []

    # Keys in builder but not in plugin (will cause validation error)
    extra_keys = builder_keys - plugin_fields
    if extra_keys:
        errors.append(f"{method_name}(): unknown keys {sorted(extra_keys)}")

    return errors


def run_runtime_checks() -> list[str]:
    """Run runtime checks by actually calling builder methods.

    This catches cases that AST analysis might miss.
    """
    from fapilog import Settings, _build_pipeline_impl, _load_plugins
    from fapilog.builder import LoggerBuilder

    errors: list[str] = []

    # Test each filter builder method
    filter_tests = [
        ("with_sampling", lambda b: b.with_sampling(rate=0.5)),
        (
            "with_adaptive_sampling",
            lambda b: b.with_adaptive_sampling(
                min_rate=0.01, max_rate=1.0, target_events_per_sec=500
            ),
        ),
        ("with_trace_sampling", lambda b: b.with_trace_sampling(default_rate=0.5)),
        ("with_rate_limit", lambda b: b.with_rate_limit(capacity=100)),
        ("with_first_occurrence", lambda b: b.with_first_occurrence(window_seconds=60)),
    ]

    for method_name, builder_call in filter_tests:
        try:
            builder = builder_call(LoggerBuilder())
            settings = Settings(
                core=builder._config.get("core"),
                filter_config=builder._config.get("filter_config"),
            )
            _, _, _, _, filters, _ = _build_pipeline_impl(settings, _load_plugins)
            if not filters:
                errors.append(f"{method_name}(): filter did not load (config rejected)")
        except Exception as e:
            errors.append(f"{method_name}(): {e}")

    # Test size_guard processor
    try:
        builder = LoggerBuilder().with_size_guard(max_bytes="1 MB")
        settings = Settings(
            core=builder._config.get("core"),
            processor_config=builder._config.get("processor_config"),
        )
        _, _, _, processors, _, _ = _build_pipeline_impl(settings, _load_plugins)
        if not processors:
            errors.append("with_size_guard(): processor did not load (config rejected)")
    except Exception as e:
        errors.append(f"with_size_guard(): {e}")

    return errors


def main() -> int:
    """Run parity checks."""
    all_errors: list[str] = []

    # Parse builder AST once
    tree = get_builder_ast()

    # Check filters
    for name, (method, config_path) in FILTER_MAPPINGS.items():
        errors = check_parity(name, method, config_path, tree)
        all_errors.extend(errors)

    # Check processors
    for name, (method, config_path) in PROCESSOR_MAPPINGS.items():
        errors = check_parity(name, method, config_path, tree)
        all_errors.extend(errors)

    # Run runtime checks (most reliable)
    runtime_errors = run_runtime_checks()
    all_errors.extend(runtime_errors)

    if all_errors:
        print("Filter/processor config parity check FAILED:")
        for error in all_errors:
            print(f"  - {error}")
        return 1

    print("Filter/processor config parity check passed ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
