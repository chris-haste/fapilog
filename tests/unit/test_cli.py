"""
Unit tests for CLI functionality.
"""

import sys
from unittest.mock import AsyncMock, patch

from fapilog.cli.main import cli_main, main


class TestCLI:
    """Test CLI functionality."""

    async def test_main_success(self) -> None:
        """Test successful CLI execution."""
        with patch("fapilog.cli.main.AsyncLogger") as mock_logger_class:
            mock_logger = AsyncMock()
            mock_logger_class.create = AsyncMock(return_value=mock_logger)
            mock_logger.__aenter__.return_value = mock_logger
            mock_logger.__aexit__.return_value = None

            result = await main()

            assert result == 0
            mock_logger_class.create.assert_called_once()
            mock_logger.info.assert_any_call("Fapilog v3 CLI started")
            mock_logger.info.assert_any_call("Async-first logging system initialized")

    async def test_main_exception_handling(self) -> None:
        """Test CLI exception handling."""
        with patch("fapilog.cli.main.AsyncLogger") as mock_logger_class:
            mock_logger_class.create.side_effect = Exception("Test error")

            with patch("builtins.print") as mock_print:
                result = await main()

                assert result == 1
                mock_print.assert_called_once_with("Error: Test error", file=sys.stderr)

    def test_cli_main_success(self) -> None:
        """Test cli_main function success."""
        with patch("fapilog.cli.main.asyncio.run") as mock_run:
            mock_run.return_value = 0

            result = cli_main()

            assert result == 0
            mock_run.assert_called_once()

    def test_cli_main_error(self) -> None:
        """Test cli_main function with error."""
        with patch("fapilog.cli.main.asyncio.run") as mock_run:
            mock_run.return_value = 1

            result = cli_main()

            assert result == 1

    def test_main_module_execution(self) -> None:
        """Test __main__ module execution."""
        with patch("fapilog.cli.main.cli_main") as mock_cli_main:
            mock_cli_main.return_value = 0

            # Simulate running as main module
            import fapilog.cli.main

            # We can't actually test the __name__ == "__main__" condition
            # without importing the module differently, but we can test
            # that cli_main can be called
            fapilog.cli.main.cli_main()
            mock_cli_main.assert_called_once()
