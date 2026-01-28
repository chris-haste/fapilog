"""Tests for scripts/check_doc_accuracy.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


class TestCheckRedactionFailModeDocs:
    """Tests for check_redaction_fail_mode_docs function."""

    def test_passes_when_docs_match_code_default(self, tmp_path: Path) -> None:
        """Check passes when docs correctly document the 'warn' default."""
        from scripts.check_doc_accuracy import check_redaction_fail_mode_docs

        # Create docs file with correct default
        doc_file = tmp_path / "docs" / "redaction" / "behavior.md"
        doc_file.parent.mkdir(parents=True)
        doc_file.write_text(
            'By default (`redaction_fail_mode="warn"`), if the redaction pipeline '
            "encounters an unexpected error, the original log event passes through."
        )

        with patch(
            "scripts.check_doc_accuracy.Path",
            return_value=doc_file,
        ):
            # Patch Path to return our temp file for the specific path check
            original_path = Path

            def patched_path(path_str: str) -> Path:
                if path_str == "docs/redaction/behavior.md":
                    return doc_file
                return original_path(path_str)

            with patch("scripts.check_doc_accuracy.Path", side_effect=patched_path):
                result = check_redaction_fail_mode_docs()

        assert result.passed is True
        assert result.errors == []
        assert "redaction" in result.name.lower()

    def test_fails_when_docs_claim_wrong_default(self, tmp_path: Path) -> None:
        """Check fails when docs claim 'open' but code defaults to 'warn'."""
        from scripts.check_doc_accuracy import check_redaction_fail_mode_docs

        # Create docs file with wrong default
        doc_file = tmp_path / "docs" / "redaction" / "behavior.md"
        doc_file.parent.mkdir(parents=True)
        doc_file.write_text(
            'By default (`redaction_fail_mode="open"`), if the redaction pipeline '
            "encounters an unexpected error, the original log event passes through."
        )

        original_path = Path

        def patched_path(path_str: str) -> Path:
            if path_str == "docs/redaction/behavior.md":
                return doc_file
            return original_path(path_str)

        with patch("scripts.check_doc_accuracy.Path", side_effect=patched_path):
            result = check_redaction_fail_mode_docs()

        assert result.passed is False
        assert len(result.errors) == 1
        assert "open" in result.errors[0]
        assert "warn" in result.errors[0]

    def test_fails_when_docs_file_missing(self, tmp_path: Path) -> None:
        """Check fails when docs/redaction/behavior.md is missing."""
        from scripts.check_doc_accuracy import check_redaction_fail_mode_docs

        # Point to non-existent file
        missing_file = tmp_path / "docs" / "redaction" / "behavior.md"

        original_path = Path

        def patched_path(path_str: str) -> Path:
            if path_str == "docs/redaction/behavior.md":
                return missing_file
            return original_path(path_str)

        with patch("scripts.check_doc_accuracy.Path", side_effect=patched_path):
            result = check_redaction_fail_mode_docs()

        assert result.passed is False
        assert len(result.errors) == 1
        assert "not found" in result.errors[0]
