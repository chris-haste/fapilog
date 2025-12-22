from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest


def _load_extract_latest_section(script_path: Path):
    mod = SourceFileLoader("extract_latest_changelog", str(script_path)).load_module()
    return mod.extract_latest_section


def test_extract_latest_section_success(tmp_path: Path) -> None:
    extract_latest_section = _load_extract_latest_section(
        Path(__file__).parents[2] / "scripts" / "extract_latest_changelog.py"
    )
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "# Changelog\n\n## [0.3.1] - Docs\n- Foo\n\n## [0.3.0] - Init\n- Bar\n",
        encoding="utf-8",
    )

    latest = extract_latest_section(changelog)
    assert "0.3.1" in latest
    assert "Foo" in latest
    assert "0.3.0" not in latest


def test_extract_latest_section_missing_section(tmp_path: Path) -> None:
    extract_latest_section = _load_extract_latest_section(
        Path(__file__).parents[2] / "scripts" / "extract_latest_changelog.py"
    )
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\nNo sections here.", encoding="utf-8")
    with pytest.raises(RuntimeError):
        extract_latest_section(changelog)
