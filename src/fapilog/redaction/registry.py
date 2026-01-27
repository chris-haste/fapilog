"""Registry functions for redaction presets.

Provides lookup, filtering, and resolution functions for preset management.
"""

from __future__ import annotations

from functools import lru_cache

from .presets import BUILTIN_PRESETS, RedactionPreset


def get_redaction_preset(name: str) -> RedactionPreset:
    """Get a preset by name.

    Args:
        name: The preset name (e.g., "GDPR_PII", "HIPAA_PHI").

    Returns:
        The RedactionPreset instance.

    Raises:
        ValueError: If the preset name is not found.
    """
    if name not in BUILTIN_PRESETS:
        valid = ", ".join(sorted(BUILTIN_PRESETS.keys()))
        raise ValueError(f"Unknown redaction preset '{name}'. Available: {valid}")
    return BUILTIN_PRESETS[name]


def list_redaction_presets() -> list[str]:
    """List all available preset names.

    Returns:
        Sorted list of preset names.
    """
    return sorted(BUILTIN_PRESETS.keys())


@lru_cache(maxsize=32)
def resolve_preset_fields(name: str) -> tuple[frozenset[str], frozenset[str]]:
    """Resolve all fields and patterns including inherited ones.

    Cached for performance - inheritance resolution happens once per preset.

    Args:
        name: The preset name to resolve.

    Returns:
        Tuple of (frozenset of fields, frozenset of patterns).

    Raises:
        ValueError: If the preset name is not found or has circular inheritance.
    """
    preset = get_redaction_preset(name)
    fields, patterns = preset.resolve(BUILTIN_PRESETS)
    return frozenset(fields), frozenset(patterns)


def get_presets_by_regulation(regulation: str) -> list[str]:
    """Get preset names matching a regulation.

    Args:
        regulation: Regulation name (e.g., "GDPR", "HIPAA", "CCPA").

    Returns:
        List of matching preset names.
    """
    return [
        name
        for name, preset in BUILTIN_PRESETS.items()
        if preset.regulation == regulation
    ]


def get_presets_by_region(region: str) -> list[str]:
    """Get preset names matching a region.

    Args:
        region: Region code (e.g., "US", "UK", "EU", "US-CA").

    Returns:
        List of matching preset names.
    """
    return [name for name, preset in BUILTIN_PRESETS.items() if preset.region == region]


def get_presets_by_tag(tag: str) -> list[str]:
    """Get preset names containing a tag.

    Args:
        tag: Tag to filter by (e.g., "pii", "healthcare", "financial").

    Returns:
        List of matching preset names.
    """
    return [name for name, preset in BUILTIN_PRESETS.items() if tag in preset.tags]
