"""Tests for scripts/check_plugin_versions.py."""

from pathlib import Path

import pytest


class TestParseVersion:
    """Tests for parse_version function."""

    def test_parses_major_minor_patch(self) -> None:
        """Should parse standard semver format."""
        from scripts.check_plugin_versions import parse_version

        assert parse_version("0.3.5") == (0, 3, 5)

    def test_parses_major_minor_only(self) -> None:
        """Should parse two-part version."""
        from scripts.check_plugin_versions import parse_version

        assert parse_version("1.0") == (1, 0)

    def test_parses_single_digit(self) -> None:
        """Should parse single version number."""
        from scripts.check_plugin_versions import parse_version

        assert parse_version("2") == (2,)


class TestVersionComparison:
    """Tests for version comparison logic."""

    def test_detects_higher_version(self) -> None:
        """Should identify when claimed version exceeds current."""
        from scripts.check_plugin_versions import parse_version

        current = parse_version("0.3.5")
        claimed = parse_version("0.4.0")
        assert claimed > current

    def test_accepts_lower_version(self) -> None:
        """Should accept versions lower than current."""
        from scripts.check_plugin_versions import parse_version

        current = parse_version("0.3.5")
        claimed = parse_version("0.3.0")
        assert claimed <= current

    def test_accepts_equal_version(self) -> None:
        """Should accept version equal to current."""
        from scripts.check_plugin_versions import parse_version

        current = parse_version("0.3.5")
        claimed = parse_version("0.3.5")
        assert claimed <= current


class TestCheckPluginFile:
    """Tests for checking individual plugin files."""

    def test_detects_future_version_in_metadata(self, tmp_path: Path) -> None:
        """Should detect min_fapilog_version exceeding current."""
        from scripts.check_plugin_versions import check_plugin_file

        plugin_file = tmp_path / "test_plugin.py"
        plugin_file.write_text("""
PLUGIN_METADATA = {
    "name": "test",
    "compatibility": {"min_fapilog_version": "0.4.0"},
}
""")
        errors = check_plugin_file(plugin_file, "0.3.5")
        assert len(errors) == 1
        assert "0.4.0" in errors[0]
        assert "0.3.5" in errors[0]

    def test_accepts_valid_version(self, tmp_path: Path) -> None:
        """Should accept min_fapilog_version at or below current."""
        from scripts.check_plugin_versions import check_plugin_file

        plugin_file = tmp_path / "test_plugin.py"
        plugin_file.write_text("""
PLUGIN_METADATA = {
    "name": "test",
    "compatibility": {"min_fapilog_version": "0.3.0"},
}
""")
        errors = check_plugin_file(plugin_file, "0.3.5")
        assert errors == []

    def test_handles_missing_metadata(self, tmp_path: Path) -> None:
        """Should handle files without plugin metadata."""
        from scripts.check_plugin_versions import check_plugin_file

        plugin_file = tmp_path / "test_plugin.py"
        plugin_file.write_text("# Just a comment")
        errors = check_plugin_file(plugin_file, "0.3.5")
        assert errors == []

    def test_handles_unreadable_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Should handle file read errors gracefully."""
        from scripts.check_plugin_versions import check_plugin_file

        # Create a non-existent path
        plugin_file = tmp_path / "nonexistent.py"
        errors = check_plugin_file(plugin_file, "0.3.5")
        assert errors == []
        captured = capsys.readouterr()
        assert "Error reading" in captured.err


class TestCheckPluginsDirectory:
    """Tests for checking all plugins in a directory."""

    def test_finds_all_violations(self, tmp_path: Path) -> None:
        """Should find violations in multiple files."""
        from scripts.check_plugin_versions import check_plugins_directory

        # Create directory structure
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        (plugins_dir / "good.py").write_text("""
PLUGIN_METADATA = {"compatibility": {"min_fapilog_version": "0.3.0"}}
""")
        (plugins_dir / "bad.py").write_text("""
PLUGIN_METADATA = {"compatibility": {"min_fapilog_version": "0.4.0"}}
""")

        errors = check_plugins_directory(plugins_dir, "0.3.5")
        assert len(errors) == 1
        assert "bad.py" in errors[0]

    def test_searches_subdirectories(self, tmp_path: Path) -> None:
        """Should recursively search subdirectories."""
        from scripts.check_plugin_versions import check_plugins_directory

        plugins_dir = tmp_path / "plugins"
        subdir = plugins_dir / "filters"
        subdir.mkdir(parents=True)

        (subdir / "level.py").write_text("""
PLUGIN_METADATA = {"compatibility": {"min_fapilog_version": "0.5.0"}}
""")

        errors = check_plugins_directory(plugins_dir, "0.3.5")
        assert len(errors) == 1
        assert "level.py" in errors[0]

    def test_skips_dotfiles(self, tmp_path: Path) -> None:
        """Should skip files starting with dot."""
        from scripts.check_plugin_versions import check_plugins_directory

        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        # Create dotfile with violation (should be skipped)
        (plugins_dir / ".hidden.py").write_text("""
PLUGIN_METADATA = {"compatibility": {"min_fapilog_version": "0.4.0"}}
""")

        errors = check_plugins_directory(plugins_dir, "0.3.5")
        assert errors == []

    def test_skips_pycache_directories(self, tmp_path: Path) -> None:
        """Should skip __pycache__ directories."""
        from scripts.check_plugin_versions import check_plugins_directory

        plugins_dir = tmp_path / "plugins"
        pycache = plugins_dir / "__pycache__"
        pycache.mkdir(parents=True)

        # Create file in __pycache__ with violation (should be skipped)
        (pycache / "cached.py").write_text("""
PLUGIN_METADATA = {"compatibility": {"min_fapilog_version": "0.4.0"}}
""")

        errors = check_plugins_directory(plugins_dir, "0.3.5")
        assert errors == []


class TestMain:
    """Tests for main entry point."""

    def test_returns_zero_when_all_valid(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should return 0 exit code when no violations."""
        from scripts.check_plugin_versions import main

        plugins_dir = tmp_path / "src" / "fapilog" / "plugins"
        plugins_dir.mkdir(parents=True)
        (plugins_dir / "valid.py").write_text("""
PLUGIN_METADATA = {"compatibility": {"min_fapilog_version": "0.3.0"}}
""")

        monkeypatch.chdir(tmp_path)
        result = main()
        assert result == 0

    def test_returns_one_when_violations_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should return 1 exit code when violations found."""
        from scripts.check_plugin_versions import main

        plugins_dir = tmp_path / "src" / "fapilog" / "plugins"
        plugins_dir.mkdir(parents=True)
        (plugins_dir / "invalid.py").write_text("""
PLUGIN_METADATA = {"compatibility": {"min_fapilog_version": "99.0.0"}}
""")

        monkeypatch.chdir(tmp_path)
        result = main()
        assert result == 1

    def test_returns_zero_when_plugins_dirs_missing(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return 0 when plugin directories don't exist."""
        from scripts.check_plugin_versions import main

        # tmp_path has no src/fapilog/plugins or packages/
        monkeypatch.chdir(tmp_path)
        result = main()
        assert result == 0
        captured = capsys.readouterr()
        assert "All plugins claim valid versions" in captured.out
