#!/usr/bin/env python3
"""
Format changelog section as Discord embed JSON.

Usage:
    python scripts/format_discord_release.py RELEASE_NOTES.md VERSION RELEASE_URL

Outputs JSON payload for Discord API with embed formatting.
"""

import json
import re
import sys
from pathlib import Path

# Discord embed color (blue)
EMBED_COLOR = 0x5865F2

# Branding
LANDING_PAGE_URL = "https://fapilog.dev"


def parse_changelog_sections(content: str) -> dict[str, list[str]]:
    """Parse changelog into category -> items mapping."""
    sections: dict[str, list[str]] = {}
    current_section = None
    current_items: list[str] = []

    for line in content.splitlines():
        # Match ### Category headers
        if line.startswith("### "):
            if current_section and current_items:
                sections[current_section] = current_items
            current_section = line[4:].strip()
            current_items = []
        # Match list items (- **...**)
        elif line.startswith("- ") and current_section:
            # Extract just the title part for brevity
            # Format: "- **Scope - Title:** Description..."
            match = re.match(r"^- \*\*(.+?):?\*\*:?\s*(.*)$", line)
            if match:
                title = match.group(1).rstrip(":")
                # Truncate long descriptions
                desc = match.group(2)
                if len(desc) > 100:
                    desc = desc[:97] + "..."
                if desc:
                    current_items.append(f"**{title}:** {desc}")
                else:
                    current_items.append(f"**{title}**")
            else:
                # Fallback for non-standard format
                current_items.append(line[2:])

    # Don't forget the last section
    if current_section and current_items:
        sections[current_section] = current_items

    return sections


def build_embed(version: str, release_url: str, sections: dict[str, list[str]]) -> dict:
    """Build Discord embed object."""
    embed: dict = {
        "title": f"\U0001f680 Fapilog v{version} Released",
        "url": release_url,
        "color": EMBED_COLOR,
        "author": {
            "name": "fapilog.dev",
            "url": LANDING_PAGE_URL,
        },
        "fields": [],
    }

    # Add fields for each category (Discord limit: 25 fields, 1024 chars per value)
    category_order = [
        "Breaking Changes",
        "Added",
        "Changed",
        "Fixed",
        "Documentation",
    ]

    # Use em-space (\u2003) for visual indentation
    indent = "\u2003"

    for category in category_order:
        if category not in sections:
            continue
        items = sections[category]
        # Format as indented bullet list
        value = "\n".join(f"{indent}\u2022 {item}" for item in items)
        # Truncate if too long
        if len(value) > 1000:
            value = value[:997] + "..."
        embed["fields"].append({"name": category, "value": value, "inline": False})

    # Add install instructions as footer
    embed["footer"] = {
        "text": f"\U0001f4e6 pip install fapilog=={version}  \u2022  fapilog.dev"
    }

    return embed


def main() -> None:
    if len(sys.argv) != 4:
        print(
            "Usage: format_discord_release.py RELEASE_NOTES.md VERSION RELEASE_URL",
            file=sys.stderr,
        )
        sys.exit(1)

    notes_path = Path(sys.argv[1])
    version = sys.argv[2]
    release_url = sys.argv[3]

    if not notes_path.exists():
        print(f"Release notes not found: {notes_path}", file=sys.stderr)
        sys.exit(1)

    content = notes_path.read_text(encoding="utf-8")

    # Skip the version header line (## [x.y.z] - date)
    lines = content.splitlines()
    if lines and lines[0].startswith("## ["):
        content = "\n".join(lines[1:])

    sections = parse_changelog_sections(content)

    if not sections:
        print("No changelog sections found", file=sys.stderr)
        sys.exit(1)

    embed = build_embed(version, release_url, sections)
    payload = {"embeds": [embed]}

    print(json.dumps(payload))


if __name__ == "__main__":
    main()
