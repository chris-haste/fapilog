"""Tests for diagnostics output stream configuration (Story 6.11)."""

from __future__ import annotations

import sys
from io import StringIO
from unittest.mock import patch

import pytest

from fapilog.core import diagnostics as diag
from fapilog.core.settings import CoreSettings, Settings


class TestDiagnosticsOutputSettings:
    """Test diagnostics_output configuration in settings."""

    def test_core_settings_diagnostics_output_defaults_to_stderr(self) -> None:
        """AC2: Default diagnostics output is stderr."""
        settings = CoreSettings()
        assert settings.diagnostics_output == "stderr"

    def test_core_settings_diagnostics_output_accepts_stdout(self) -> None:
        """AC2: Opt-in stdout for backward compatibility."""
        settings = CoreSettings(diagnostics_output="stdout")
        assert settings.diagnostics_output == "stdout"

    def test_settings_core_diagnostics_output_defaults_to_stderr(self) -> None:
        """AC2: Top-level Settings exposes diagnostics_output via core."""
        settings = Settings()
        assert settings.core.diagnostics_output == "stderr"

    def test_settings_core_diagnostics_output_configurable(self) -> None:
        """AC2: Can configure via nested core dict."""
        settings = Settings(core={"diagnostics_output": "stdout"})
        assert settings.core.diagnostics_output == "stdout"

    def test_core_settings_rejects_invalid_diagnostics_output(self) -> None:
        """Only stderr and stdout are valid values."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="diagnostics_output"):
            CoreSettings(diagnostics_output="file")  # type: ignore[arg-type]


class TestDiagnosticsWriterOutput:
    """Test that diagnostics actually write to the configured stream."""

    def test_default_writer_outputs_to_stderr(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC1: Diagnostics write to stderr by default."""
        monkeypatch.setattr(diag, "_is_enabled", lambda: True)
        diag._reset_for_tests()

        captured = StringIO()
        with patch.object(sys, "stderr", captured):
            diag._default_writer({"message": "test"})

        output = captured.getvalue()
        assert "test" in output
        assert output.endswith("\n")

    def test_default_writer_uses_compact_json(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify output is compact JSON (no extra whitespace)."""
        monkeypatch.setattr(diag, "_is_enabled", lambda: True)
        diag._reset_for_tests()

        captured = StringIO()
        with patch.object(sys, "stderr", captured):
            diag._default_writer({"key": "value", "num": 42})

        output = captured.getvalue().strip()
        # Compact JSON should have no spaces after separators
        assert output == '{"key":"value","num":42}'

    def test_emit_outputs_to_stderr_by_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC1: Full emit path writes to stderr."""
        monkeypatch.setattr(diag, "_is_enabled", lambda: True)
        diag._reset_for_tests()

        # Reset writer to default
        diag._writer = diag._default_writer

        captured = StringIO()
        with patch.object(sys, "stderr", captured):
            diag.emit(component="test", level="DEBUG", message="hello stderr")

        output = captured.getvalue()
        assert "hello stderr" in output
