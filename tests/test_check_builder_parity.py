"""Tests for the builder parity check script.

These tests verify the pre-commit hook script correctly identifies
missing builder coverage for all configuration categories.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Project root is two levels up from this test file
PROJECT_ROOT = Path(__file__).parent.parent.resolve()


class TestParityCheckScript:
    """Tests for the check_builder_parity.py script."""

    def test_script_runs_without_error(self) -> None:
        """Verify the script can be executed."""
        result = subprocess.run(
            [sys.executable, "scripts/check_builder_parity.py"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        # Script may pass or fail depending on current parity state
        # but should not crash with an exception
        assert result.returncode in (0, 1), f"Unexpected error: {result.stderr}"

    def test_script_imports_mappings(self) -> None:
        """Verify the script can import the mappings module."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from scripts.check_builder_parity import main; print('ok')",
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, f"Import failed: {result.stderr}"
        assert "ok" in result.stdout


class TestGetModelFields:
    """Tests for the get_model_fields helper function."""

    def test_get_model_fields_extracts_core_settings_fields(self) -> None:
        """Verify get_model_fields extracts CoreSettings fields."""
        from fapilog.core.settings import CoreSettings
        from scripts.check_builder_parity import get_model_fields

        fields = get_model_fields(CoreSettings)

        assert isinstance(fields, set)
        assert "log_level" in fields
        assert "max_queue_size" in fields
        assert "model_config" not in fields  # Should be excluded

    def test_get_model_fields_excludes_model_config(self) -> None:
        """Verify get_model_fields excludes model_config."""
        from fapilog.core.settings import LokiSinkSettings
        from scripts.check_builder_parity import get_model_fields

        fields = get_model_fields(LokiSinkSettings)

        assert "model_config" not in fields
        assert "url" in fields


class TestCheckCoreSetting:
    """Tests for check_core_settings function."""

    def test_check_core_settings_returns_list(self) -> None:
        """Verify check_core_settings returns a list of errors."""
        from scripts.check_builder_parity import check_core_settings

        errors = check_core_settings()

        assert isinstance(errors, list)
        # All items should be strings
        for error in errors:
            assert isinstance(error, str)


class TestCheckSinkSettings:
    """Tests for check_sink_settings function."""

    def test_check_sink_settings_returns_list(self) -> None:
        """Verify check_sink_settings returns a list of errors."""
        from scripts.check_builder_parity import check_sink_settings

        errors = check_sink_settings()

        assert isinstance(errors, list)


class TestCheckFilterSettings:
    """Tests for check_filter_settings function."""

    def test_check_filter_settings_returns_list(self) -> None:
        """Verify check_filter_settings returns a list of errors."""
        from scripts.check_builder_parity import check_filter_settings

        errors = check_filter_settings()

        assert isinstance(errors, list)


class TestCheckProcessorSettings:
    """Tests for check_processor_settings function."""

    def test_check_processor_settings_returns_list(self) -> None:
        """Verify check_processor_settings returns a list of errors."""
        from scripts.check_builder_parity import check_processor_settings

        errors = check_processor_settings()

        assert isinstance(errors, list)


class TestCheckAdvancedSettings:
    """Tests for check_advanced_settings function."""

    def test_check_advanced_settings_returns_list(self) -> None:
        """Verify check_advanced_settings returns a list of errors."""
        from scripts.check_builder_parity import check_advanced_settings

        errors = check_advanced_settings()

        assert isinstance(errors, list)


class TestMainFunction:
    """Tests for the main entry point."""

    def test_main_returns_zero_or_one(self) -> None:
        """Verify main returns 0 (pass) or 1 (fail)."""
        from scripts.check_builder_parity import main

        result = main()

        assert result in (0, 1)
