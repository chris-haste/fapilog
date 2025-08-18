"""
Custom Sphinx extension for fapilog API documentation.

This extension parses @docs: markers from docstrings and applies
the standardized template format for API documentation.
"""

import re
from typing import Dict, List, Optional

from docutils.statemachine import ViewList
from sphinx.ext.autodoc import (
    ClassDocumenter,
    FunctionDocumenter,
    MethodDocumenter,
    ModuleDocumenter,
)


class FapilogAPIDocumenter:
    """Custom documenter that applies the fapilog API template."""

    def __init__(self):
        self.doc_markers = {"use_cases": [], "examples": [], "notes": []}

    def parse_docstring_markers(self, docstring: str) -> Dict[str, List[str]]:
        """Parse @docs: markers from docstring."""
        if not docstring:
            return {}

        markers = {}
        current_marker = None
        current_content = []

        for line in docstring.split("\n"):
            # Check for marker start
            marker_match = re.match(r"@docs:(\w+)", line.strip())
            if marker_match:
                # Save previous marker content
                if current_marker and current_content:
                    markers[current_marker] = current_content

                # Start new marker
                current_marker = marker_match.group(1)
                current_content = []
                continue

            # Check for marker end (empty line or new marker)
            if current_marker and line.strip():
                current_content.append(line.strip())
            elif current_marker and not line.strip() and current_content:
                # Empty line after content, end of marker
                markers[current_marker] = current_content
                current_marker = None
                current_content = []

        # Save final marker
        if current_marker and current_content:
            markers[current_marker] = current_content

        return markers

    def format_use_cases(self, use_cases: List[str]) -> str:
        """Format use cases section."""
        if not use_cases:
            return ""

        lines = ["## Use Cases", ""]
        for use_case in use_cases:
            lines.append(f"- {use_case}")
        lines.append("")
        return "\n".join(lines)

    def format_examples(self, examples: List[str]) -> str:
        """Format examples section."""
        if not examples:
            return ""

        lines = ["## Code Examples", ""]
        for example in examples:
            lines.append(example)
        lines.append("")
        return "\n".join(lines)

    def format_notes(self, notes: List[str]) -> str:
        """Format notes section."""
        if not notes:
            return ""

        lines = ["## Notes", ""]
        for note in notes:
            lines.append(f"- {note}")
        lines.append("")
        return "\n".join(lines)

    def apply_template(self, docstring: str, markers: Dict[str, List[str]]) -> str:
        """Apply the fapilog API template to the docstring."""
        # Remove @docs: markers from the main description
        clean_docstring = re.sub(
            r"@docs:\w+.*?(?=\n\s*\n|\n\s*$)", "", docstring, flags=re.DOTALL
        )
        clean_docstring = clean_docstring.strip()

        # Build the formatted documentation
        sections = []

        # Description (from cleaned docstring)
        if clean_docstring:
            sections.append(f"## Description\n\n{clean_docstring}\n")

        # Use Cases
        if "use_cases" in markers:
            sections.append(self.format_use_cases(markers["use_cases"]))

        # Examples
        if "examples" in markers:
            sections.append(self.format_examples(markers["examples"]))

        # Notes
        if "notes" in markers:
            sections.append(self.format_notes(markers["notes"]))

        return "\n".join(sections)


class FapilogModuleDocumenter(ModuleDocumenter):
    """Custom module documenter with fapilog template."""

    def add_content(self, more_content: Optional[ViewList]) -> None:
        """Override to apply custom template."""
        # Get the original docstring
        docstring = self.get_doc()
        if docstring:
            docstring = "\n".join(docstring[0])

            # Parse @docs: markers
            api_doc = FapilogAPIDocumenter()
            markers = api_doc.parse_docstring_markers(docstring)

            # Apply template
            formatted_doc = api_doc.apply_template(docstring, markers)

            # Create new content
            if formatted_doc:
                new_content = ViewList()
                for line in formatted_doc.split("\n"):
                    new_content.append(line, "")

                # Call parent with new content
                super().add_content(new_content)
                return

        # Fall back to original behavior
        super().add_content(more_content)


class FapilogClassDocumenter(ClassDocumenter):
    """Custom class documenter with fapilog template."""

    def add_content(self, more_content: Optional[ViewList]) -> None:
        """Override to apply custom template."""
        # Get the original docstring
        docstring = self.get_doc()
        if docstring:
            docstring = "\n".join(docstring[0])

            # Parse @docs: markers
            api_doc = FapilogAPIDocumenter()
            markers = api_doc.parse_docstring_markers(docstring)

            # Apply template
            formatted_doc = api_doc.apply_template(docstring, markers)

            # Create new content
            if formatted_doc:
                new_content = ViewList()
                for line in formatted_doc.split("\n"):
                    new_content.append(line, "")

                # Call parent with new content
                super().add_content(new_content)
                return

        # Fall back to original behavior
        super().add_content(more_content)


class FapilogFunctionDocumenter(FunctionDocumenter):
    """Custom function documenter with fapilog template."""

    def add_content(self, more_content: Optional[ViewList]) -> None:
        """Override to apply custom template."""
        # Get the original docstring
        docstring = self.get_doc()
        if docstring:
            docstring = "\n".join(docstring[0])

            # Parse @docs: markers
            api_doc = FapilogAPIDocumenter()
            markers = api_doc.parse_docstring_markers(docstring)

            # Apply template
            formatted_doc = api_doc.apply_template(docstring, markers)

            # Create new content
            if formatted_doc:
                new_content = ViewList()
                for line in formatted_doc.split("\n"):
                    new_content.append(line, "")

                # Call parent with new content
                super().add_content(new_content)
                return

        # Fall back to original behavior
        super().add_content(more_content)


class FapilogMethodDocumenter(MethodDocumenter):
    """Custom method documenter with fapilog template."""

    def add_content(self, more_content: Optional[ViewList]) -> None:
        """Override to apply custom template."""
        # Get the original docstring
        docstring = self.get_doc()
        if docstring:
            docstring = "\n".join(docstring[0])

            # Parse @docs: markers
            api_doc = FapilogAPIDocumenter()
            markers = api_doc.parse_docstring_markers(docstring)

            # Apply template
            formatted_doc = api_doc.apply_template(docstring, markers)

            # Create new content
            if formatted_doc:
                new_content = ViewList()
                for line in formatted_doc.split("\n"):
                    new_content.append(line, "")

                # Call parent with new content
                super().add_content(new_content)
                return

        # Fall back to original behavior
        super().add_content(more_content)


def setup(app):
    """Setup the custom autodoc extension."""
    # Register custom documenters
    app.add_autodocumenter(FapilogModuleDocumenter, override=True)
    app.add_autodocumenter(FapilogClassDocumenter, override=True)
    app.add_autodocumenter(FapilogFunctionDocumenter, override=True)
    app.add_autodocumenter(FapilogMethodDocumenter, override=True)

    return {
        "version": "1.0.0",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
