"""Tests for lifecycle.install_signal_handlers deprecation (Story 4.55 AC6)."""

from __future__ import annotations

import warnings
from unittest.mock import MagicMock


class TestInstallSignalHandlersDeprecation:
    """AC6: lifecycle.install_signal_handlers() is deprecated."""

    def test_install_signal_handlers_emits_deprecation_warning(self) -> None:
        """Calling install_signal_handlers should emit DeprecationWarning."""
        from fapilog.core.lifecycle import install_signal_handlers

        mock_logger = MagicMock()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            install_signal_handlers(mock_logger)

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()
            assert "install_shutdown_handlers" in str(w[0].message)

    def test_deprecation_warning_mentions_replacement(self) -> None:
        """Deprecation warning should mention the replacement function."""
        from fapilog.core.lifecycle import install_signal_handlers

        mock_logger = MagicMock()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            install_signal_handlers(mock_logger)

            warning_message = str(w[0].message)
            assert "fapilog.install_shutdown_handlers" in warning_message

    def test_deprecated_function_still_works(self) -> None:
        """Deprecated function should still install handlers for backwards compat."""
        from unittest.mock import patch

        from fapilog.core.lifecycle import install_signal_handlers

        mock_logger = MagicMock()

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            with patch("fapilog.core.lifecycle.signal") as mock_signal:
                install_signal_handlers(mock_logger)

                # Should still attempt to install signal handlers (SIGTERM and SIGINT)
                assert mock_signal.signal.call_count == 2

    def test_deprecation_warning_stacklevel_correct(self) -> None:
        """Warning should point to caller, not the function itself."""
        from fapilog.core.lifecycle import install_signal_handlers

        mock_logger = MagicMock()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            install_signal_handlers(mock_logger)  # This line should be in warning

            # The filename in the warning should be this test file
            assert "test_lifecycle_deprecation" in w[0].filename
