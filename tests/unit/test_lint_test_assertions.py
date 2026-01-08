"""Unit tests for scripts/lint_test_assertions.py."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

# Add scripts directory to path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from lint_test_assertions import (
    Violation,
    format_baseline_key,
    lint_file,
    load_baseline,
)


class TestWeakAssertionVisitor:
    """Tests for WeakAssertionVisitor AST detection."""

    def test_detects_gte_zero(self, tmp_path: Path) -> None:
        """WA001: assert x >= 0 should be detected."""
        source = textwrap.dedent("""
            def test_example():
                result = 5
                assert result >= 0
        """)
        test_file = tmp_path / "test_example.py"
        test_file.write_text(source)

        violations = lint_file(test_file)

        assert len(violations) == 1
        assert violations[0].code == "WA001"
        assert violations[0].line == 4

    def test_detects_gte_one(self, tmp_path: Path) -> None:
        """WA002: assert x >= 1 should be detected."""
        source = textwrap.dedent("""
            def test_example():
                count = 3
                assert count >= 1
        """)
        test_file = tmp_path / "test_example.py"
        test_file.write_text(source)

        violations = lint_file(test_file)

        assert len(violations) == 1
        assert violations[0].code == "WA002"
        assert violations[0].line == 4

    def test_detects_is_not_none(self, tmp_path: Path) -> None:
        """WA003: assert x is not None should be detected."""
        source = textwrap.dedent("""
            def test_example():
                obj = object()
                assert obj is not None
        """)
        test_file = tmp_path / "test_example.py"
        test_file.write_text(source)

        violations = lint_file(test_file)

        assert len(violations) == 1
        assert violations[0].code == "WA003"
        assert violations[0].line == 4

    def test_ignores_strong_assertions(self, tmp_path: Path) -> None:
        """Strong assertions should not trigger violations."""
        source = textwrap.dedent("""
            def test_example():
                result = 5
                assert result == 5
                assert result > 0
                assert result < 10
                assert result != 0
        """)
        test_file = tmp_path / "test_example.py"
        test_file.write_text(source)

        violations = lint_file(test_file)

        assert len(violations) == 0

    def test_noqa_suppresses_wa001(self, tmp_path: Path) -> None:
        """# noqa: WA001 should suppress WA001 violation."""
        source = textwrap.dedent("""
            def test_example():
                result = 5
                assert result >= 0  # noqa: WA001
        """)
        test_file = tmp_path / "test_example.py"
        test_file.write_text(source)

        violations = lint_file(test_file)

        assert len(violations) == 0

    def test_noqa_suppresses_wa002(self, tmp_path: Path) -> None:
        """# noqa: WA002 should suppress WA002 violation."""
        source = textwrap.dedent("""
            def test_example():
                count = 3
                assert count >= 1  # noqa: WA002
        """)
        test_file = tmp_path / "test_example.py"
        test_file.write_text(source)

        violations = lint_file(test_file)

        assert len(violations) == 0

    def test_noqa_suppresses_wa003(self, tmp_path: Path) -> None:
        """# noqa: WA003 should suppress WA003 violation."""
        source = textwrap.dedent("""
            def test_example():
                obj = object()
                assert obj is not None  # noqa: WA003
        """)
        test_file = tmp_path / "test_example.py"
        test_file.write_text(source)

        violations = lint_file(test_file)

        assert len(violations) == 0

    def test_blanket_noqa_suppresses_all(self, tmp_path: Path) -> None:
        """# noqa (blanket) should suppress any violation."""
        source = textwrap.dedent("""
            def test_example():
                result = 5
                assert result >= 0  # noqa
        """)
        test_file = tmp_path / "test_example.py"
        test_file.write_text(source)

        violations = lint_file(test_file)

        assert len(violations) == 0

    def test_noqa_with_multiple_codes(self, tmp_path: Path) -> None:
        """# noqa: WA001, WA002 should suppress both codes."""
        source = textwrap.dedent("""
            def test_example():
                result = 5
                assert result >= 0  # noqa: WA001, WA002
        """)
        test_file = tmp_path / "test_example.py"
        test_file.write_text(source)

        violations = lint_file(test_file)

        assert len(violations) == 0

    def test_detects_multiple_violations(self, tmp_path: Path) -> None:
        """Multiple violations in one file should all be detected."""
        source = textwrap.dedent("""
            def test_example():
                result = 5
                assert result >= 0
                assert result >= 1
                assert result is not None
        """)
        test_file = tmp_path / "test_example.py"
        test_file.write_text(source)

        violations = lint_file(test_file)

        assert len(violations) == 3
        codes = {v.code for v in violations}
        assert codes == {"WA001", "WA002", "WA003"}

    def test_handles_async_functions(self, tmp_path: Path) -> None:
        """Violations in async functions should be detected."""
        source = textwrap.dedent("""
            async def test_async_example():
                result = 5
                assert result >= 0
        """)
        test_file = tmp_path / "test_example.py"
        test_file.write_text(source)

        violations = lint_file(test_file)

        assert len(violations) == 1
        assert violations[0].code == "WA001"


class TestLintFile:
    """Tests for lint_file function."""

    def test_handles_syntax_error(self, tmp_path: Path) -> None:
        """Files with syntax errors should return empty list."""
        test_file = tmp_path / "test_invalid.py"
        test_file.write_text("def broken(\n")

        violations = lint_file(test_file)

        assert violations == []

    def test_handles_missing_file(self, tmp_path: Path) -> None:
        """Missing files should return empty list."""
        violations = lint_file(tmp_path / "nonexistent.py")

        assert violations == []


class TestLoadBaseline:
    """Tests for baseline file loading."""

    def test_loads_baseline_entries(self, tmp_path: Path) -> None:
        """Baseline file entries should be loaded as file:line keys."""
        baseline_file = tmp_path / "baseline.txt"
        baseline_file.write_text(
            "# Comment\n"
            "tests/test_foo.py:10  # WA001\n"
            "tests/test_bar.py:20  # WA002\n"
            "\n"
        )

        baselined = load_baseline(baseline_file)

        assert "tests/test_foo.py:10" in baselined
        assert "tests/test_bar.py:20" in baselined
        assert len(baselined) == 2

    def test_ignores_comments_and_blank_lines(self, tmp_path: Path) -> None:
        """Comments and blank lines should be ignored."""
        baseline_file = tmp_path / "baseline.txt"
        baseline_file.write_text(
            "# Header comment\n\n# Another comment\ntests/test_foo.py:10  # WA001\n"
        )

        baselined = load_baseline(baseline_file)

        assert len(baselined) == 1
        assert "tests/test_foo.py:10" in baselined

    def test_handles_missing_baseline(self, tmp_path: Path) -> None:
        """Missing baseline file should return empty set."""
        baselined = load_baseline(tmp_path / "nonexistent.txt")

        assert baselined == set()


class TestFormatBaselineKey:
    """Tests for baseline key formatting."""

    def test_formats_violation_as_file_line(self) -> None:
        """Violation should be formatted as file:line."""
        violation = Violation(
            file=Path("tests/test_foo.py"),
            line=42,
            code="WA001",
            message="test message",
            suggestion="test suggestion",
        )

        key = format_baseline_key(violation)

        assert key == "tests/test_foo.py:42"
