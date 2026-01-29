#!/usr/bin/env python3
"""
Extract the latest changelog section for GitHub release notes.

Usage:
    python scripts/extract_latest_changelog.py CHANGELOG.md OUTPUT.md

Behavior:
- Finds the first top-level heading (## ...) after the initial title (# ...).
- Writes that section (up to the next ## or EOF) to OUTPUT.
- Exits non-zero if no section is found.
"""

import sys
from pathlib import Path


def extract_latest_section(changelog: Path) -> str:
    lines = changelog.read_text(encoding="utf-8").splitlines()
    section_lines: list[str] = []
    in_section = False
    saw_title = False
    for line in lines:
        if line.startswith("# "):
            saw_title = True
            continue
        if not saw_title:
            continue
        if line.startswith("## "):
            # Skip [Unreleased] section
            if "[Unreleased]" in line:
                continue
            if not in_section:
                in_section = True
                section_lines.append(line)
                continue
            else:
                break
        if in_section:
            section_lines.append(line)
    if not section_lines:
        raise RuntimeError("No changelog section found")
    # Trim trailing blank lines
    while section_lines and section_lines[-1].strip() == "":
        section_lines.pop()
    return "\n".join(section_lines) + "\n"


def main() -> None:
    if len(sys.argv) != 3:
        print(
            "Usage: extract_latest_changelog.py CHANGELOG.md OUTPUT.md", file=sys.stderr
        )
        sys.exit(1)
    changelog = Path(sys.argv[1])
    output = Path(sys.argv[2])
    if not changelog.exists():
        print(f"Changelog not found: {changelog}", file=sys.stderr)
        sys.exit(1)
    try:
        latest = extract_latest_section(changelog)
        output.write_text(latest, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to extract changelog: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
