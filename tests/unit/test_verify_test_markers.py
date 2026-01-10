"""Unit tests for scripts/verify_test_markers.py."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

# Add scripts directory to path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from verify_test_markers import (
    check_file,
    main,
)


def _write_test(tmp_path: Path, source: str) -> Path:
    test_file = tmp_path / "test_example.py"
    test_file.write_text(textwrap.dedent(source))
    return test_file


def test_unmarked_tests_are_reported(tmp_path: Path) -> None:
    test_file = _write_test(
        tmp_path,
        """
        def test_example():
            assert True
        """,
    )

    unmarked, unknown, conflicts = check_file(test_file)

    assert len(unmarked) == 1
    assert unknown == []
    assert conflicts == []


def test_module_and_class_markers_are_inherited(tmp_path: Path) -> None:
    test_file = _write_test(
        tmp_path,
        """
        import pytest

        pytestmark = [pytest.mark.integration]

        @pytest.mark.security
        class TestSecurity:
            def test_secured(self):
                assert True
        """,
    )

    unmarked, unknown, conflicts = check_file(test_file)

    assert unmarked == []
    assert unknown == []
    assert conflicts == []


def test_unknown_marker_is_reported(tmp_path: Path) -> None:
    test_file = _write_test(
        tmp_path,
        """
        import pytest

        @pytest.mark.wat
        def test_unknown():
            assert True
        """,
    )

    unmarked, unknown, conflicts = check_file(test_file)

    assert len(unknown) == 1
    assert unknown[0].name == "test_unknown"
    assert conflicts == []


def test_flaky_cannot_be_combined_with_security(tmp_path: Path) -> None:
    test_file = _write_test(
        tmp_path,
        """
        import pytest

        @pytest.mark.security
        @pytest.mark.flaky
        def test_flaky_security():
            assert True
        """,
    )

    unmarked, unknown, conflicts = check_file(test_file)

    assert len(conflicts) == 1
    assert conflicts[0].name == "test_flaky_security"


def test_strict_mode_fails_on_unmarked(tmp_path: Path, monkeypatch) -> None:
    test_file = _write_test(
        tmp_path,
        """
        def test_example():
            assert True
        """,
    )

    monkeypatch.setenv("PYTHONHASHSEED", "0")
    monkeypatch.setattr(
        sys, "argv", ["verify_test_markers.py", "--strict", str(test_file)]
    )

    assert main() == 1


def test_non_strict_allows_unmarked(tmp_path: Path, monkeypatch) -> None:
    test_file = _write_test(
        tmp_path,
        """
        def test_example():
            assert True
        """,
    )

    monkeypatch.setattr(sys, "argv", ["verify_test_markers.py", str(test_file)])

    assert main() == 0
