#!/usr/bin/env python3
"""
Link validation script for fapilog documentation.

This script validates all internal documentation links to ensure they work correctly.
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List, Set, Tuple


class LinkValidator:
    """Validates internal documentation links."""

    def __init__(self, docs_dir: Path):
        self.docs_dir = docs_dir
        self.broken_links: List[Tuple[str, str, str]] = []
        self.valid_files: Set[str] = set()
        self.markdown_files: List[Path] = []

    def scan_markdown_files(self) -> None:
        """Scan for all markdown files in the documentation directory."""
        self.markdown_files = list(self.docs_dir.rglob("*.md"))
        print(f"Found {len(self.markdown_files)} markdown files")

    def extract_links(self, file_path: Path) -> List[Tuple[str, str]]:
        """Extract all links from a markdown file."""
        links: List[Tuple[str, str]] = []

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return links

        # Match markdown links: [text](url)
        link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
        matches = re.findall(link_pattern, content)

        for text, url in matches:
            links.append((text, url))

        # Match reference links: [text][ref] and [ref]: url
        ref_pattern = r"^\[([^\]]+)\]:\s*(.+)$"
        ref_matches = re.findall(ref_pattern, content, re.MULTILINE)

        for ref, url in ref_matches:
            links.append((ref, url))

        return links

    def validate_link(self, source_file: Path, link_text: str, url: str) -> bool:
        """Validate if a link is valid."""
        # Skip external links
        if url.startswith(("http://", "https://", "mailto:", "#")):
            return True

        # Handle anchor links
        if url.startswith("#"):
            return True

        # Handle relative links
        if url.startswith("./") or url.startswith("../"):
            target_path = source_file.parent / url
        else:
            target_path = source_file.parent / url

        # Resolve the path
        try:
            target_path = target_path.resolve()
        except Exception:
            return False

        # Check if file exists
        if target_path.exists():
            return True

        # Check if it's a directory with index.md
        if target_path.is_dir() and (target_path / "index.md").exists():
            return True

        # Check if it's a markdown file without extension
        if not target_path.suffix and (target_path.with_suffix(".md")).exists():
            return True

        return False

    def validate_file_links(self, file_path: Path) -> None:
        """Validate all links in a single file."""
        links = self.extract_links(file_path)

        for link_text, url in links:
            if not self.validate_link(file_path, link_text, url):
                self.broken_links.append(
                    (str(file_path.relative_to(self.docs_dir)), link_text, url)
                )

    def validate_all_links(self) -> None:
        """Validate links in all markdown files."""
        print("Validating internal links...")

        for file_path in self.markdown_files:
            self.validate_file_links(file_path)

    def generate_report(self) -> None:
        """Generate a report of broken links."""
        if not self.broken_links:
            print("✅ All internal links are valid!")
            return

        print(f"\n❌ Found {len(self.broken_links)} broken links:")
        print("-" * 80)

        for file_path, link_text, url in self.broken_links:
            print(f"File: {file_path}")
            print(f"Link: {link_text}")
            print(f"URL:  {url}")
            print("-" * 40)

    def run(self) -> int:
        """Run the complete validation process."""
        print("🔍 Starting link validation...")

        self.scan_markdown_files()
        self.validate_all_links()
        self.generate_report()

        return len(self.broken_links)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Validate internal markdown links")
    parser.add_argument(
        "--allow-broken",
        action="store_true",
        help="Do not fail (exit 1) when broken links are found; report only",
    )
    args = parser.parse_args()

    docs_dir = Path(".")

    if not docs_dir.exists():
        print("Error: Current directory does not exist")
        sys.exit(1)

    # Check if we're in the docs directory
    if not (docs_dir / "conf.py").exists():
        print("Error: This script must be run from the docs/ directory")
        sys.exit(1)

    validator = LinkValidator(docs_dir)
    broken_count = validator.run()

    if broken_count > 0:
        print(f"\n❌ Validation completed with {broken_count} broken links")
        sys.exit(0 if args.allow_broken else 1)
    else:
        print("\n✅ Link validation completed successfully")
        sys.exit(0)


if __name__ == "__main__":
    main()
