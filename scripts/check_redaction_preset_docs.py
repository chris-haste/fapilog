#!/usr/bin/env python3
"""Check that redaction preset documentation matches source definitions.

This script ensures docs/redaction/presets.md stays in sync with
src/fapilog/redaction/presets.py.

Usage:
    python scripts/check_redaction_preset_docs.py

Exit codes:
    0 - Documentation is in sync
    1 - Documentation is out of sync (missing or extra fields)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fapilog.redaction.presets import BUILTIN_PRESETS, RedactionPreset


def extract_fields_from_docs(docs_path: Path) -> dict[str, set[str]]:
    """Extract field lists from the presets documentation.

    Parses the markdown looking for code blocks under preset headings.

    Returns:
        Dict mapping preset name to set of documented fields.
    """
    content = docs_path.read_text()
    preset_fields: dict[str, set[str]] = {}

    # Find each preset section (#### PRESET_NAME) and its code block
    # Use a two-step approach to avoid ReDoS with nested quantifiers
    heading_pattern = re.compile(r"####\s+(\w+)\s*\n")
    code_block_pattern = re.compile(r"```\n([^`]+)\n```")

    # Find all headings and their positions
    headings = [(m.group(1), m.end()) for m in heading_pattern.finditer(content)]

    for i, (preset_name, start_pos) in enumerate(headings):
        # Search for code block between this heading and the next
        end_pos = headings[i + 1][1] if i + 1 < len(headings) else len(content)
        section = content[start_pos:end_pos]

        code_match = code_block_pattern.search(section)
        if not code_match:
            continue

        field_block = code_match.group(1)

        # Parse fields from the block (comma or newline separated)
        fields = set()
        for line in field_block.split("\n"):
            # Split by comma and clean up
            for field in line.split(","):
                field = field.strip()
                if field and not field.startswith("#"):
                    fields.add(field)

        if fields:
            preset_fields[preset_name] = fields

    return preset_fields


def get_source_fields() -> dict[str, set[str]]:
    """Get field sets from source preset definitions.

    Returns:
        Dict mapping preset name to set of fields (direct fields only,
        not inherited).
    """
    source_fields: dict[str, set[str]] = {}

    for name, preset in BUILTIN_PRESETS.items():
        # Get direct fields only (not inherited)
        source_fields[name] = set(preset.fields)

    return source_fields


def get_resolved_fields(preset: RedactionPreset) -> set[str]:
    """Get all fields for a preset including inherited ones."""
    fields, _ = preset.resolve(BUILTIN_PRESETS)
    return fields


def check_preset_sync() -> list[str]:
    """Check that documentation matches source.

    Returns:
        List of error messages, empty if in sync.
    """
    errors: list[str] = []

    docs_path = Path(__file__).parent.parent / "docs" / "redaction" / "presets.md"

    if not docs_path.exists():
        errors.append(f"Documentation file not found: {docs_path}")
        return errors

    doc_fields = extract_fields_from_docs(docs_path)
    source_fields = get_source_fields()

    # Check each source preset is documented
    for preset_name, src_fields in source_fields.items():
        preset = BUILTIN_PRESETS[preset_name]

        if preset_name not in doc_fields:
            # Presets that use inheritance show "Inherits from" instead of
            # listing all fields - this is acceptable
            if preset.extends:
                continue
            # Non-inheriting presets with fields must be documented
            if src_fields:
                errors.append(
                    f"Preset {preset_name} not documented in presets.md "
                    f"(has {len(src_fields)} fields)"
                )
            continue

        doc_set = doc_fields[preset_name]

        # For presets that inherit, the docs may show additional fields
        # that come from the "Additional fields" section. Only check that
        # the direct fields are documented.
        if preset.extends:
            # For inherited presets, just verify the direct fields are present
            # (docs may also show inherited fields, which is fine)
            missing_direct = src_fields - doc_set
            if missing_direct:
                errors.append(
                    f"Preset {preset_name}: direct fields missing from docs: "
                    f"{sorted(missing_direct)}"
                )
        else:
            # For non-inheriting presets, require exact match
            missing_in_docs = src_fields - doc_set
            if missing_in_docs:
                errors.append(
                    f"Preset {preset_name}: fields in source but not in docs: "
                    f"{sorted(missing_in_docs)}"
                )

            extra_in_docs = doc_set - src_fields
            if extra_in_docs:
                errors.append(
                    f"Preset {preset_name}: fields in docs but not in source: "
                    f"{sorted(extra_in_docs)}"
                )

    # Check for documented presets that don't exist in source
    for preset_name in doc_fields:
        if preset_name not in source_fields:
            errors.append(f"Preset {preset_name} documented but not found in source")

    return errors


def main() -> int:
    """Run the check and report results."""
    print("Checking redaction preset documentation sync...")

    errors = check_preset_sync()

    if errors:
        print("\nRedaction Preset Documentation Out of Sync\n")
        for error in errors:
            print(f"  - {error}")
        print("\nUpdate docs/redaction/presets.md to match source definitions.")
        print("See: src/fapilog/redaction/presets.py")
        return 1

    print("✓ Redaction preset documentation is in sync with source")
    return 0


if __name__ == "__main__":
    sys.exit(main())
