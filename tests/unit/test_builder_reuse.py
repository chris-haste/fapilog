"""Tests for LoggerBuilder.reuse() method (Story 10.41)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from fapilog import AsyncLoggerBuilder, LoggerBuilder


class TestReuseMethodReturns:
    """Test that reuse() returns self for chaining."""

    def test_reuse_method_returns_self(self) -> None:
        """reuse() should return self for method chaining."""
        builder = LoggerBuilder()
        result = builder.reuse(False)
        assert result is builder

    def test_reuse_method_returns_self_async_builder(self) -> None:
        """reuse() should return self for AsyncLoggerBuilder too."""
        builder = AsyncLoggerBuilder()
        result = builder.reuse(False)
        assert result is builder


class TestReuseInternalState:
    """Test that reuse() sets internal state correctly."""

    def test_reuse_false_sets_internal_flag(self) -> None:
        """reuse(False) should set _reuse to False."""
        builder = LoggerBuilder()
        builder.reuse(False)
        assert builder._reuse is False

    def test_reuse_true_sets_internal_flag(self) -> None:
        """reuse(True) should set _reuse to True."""
        builder = LoggerBuilder()
        builder.reuse(False)  # First set to False
        builder.reuse(True)  # Then back to True
        assert builder._reuse is True

    def test_default_reuse_is_true(self) -> None:
        """Default _reuse should be True."""
        builder = LoggerBuilder()
        assert builder._reuse is True


class TestReuseChaining:
    """Test that reuse() can be chained anywhere in builder chain."""

    def test_reuse_at_start_of_chain(self) -> None:
        """reuse() can be called at the start of the chain."""
        builder = AsyncLoggerBuilder().reuse(False).add_stdout()
        assert builder._reuse is False

    def test_reuse_at_end_of_chain(self) -> None:
        """reuse() can be called at the end of the chain."""
        builder = AsyncLoggerBuilder().add_stdout().reuse(False)
        assert builder._reuse is False

    def test_reuse_in_middle_of_chain(self) -> None:
        """reuse() can be called in the middle of the chain."""
        builder = AsyncLoggerBuilder().reuse(False).with_level("DEBUG").add_stdout()
        assert builder._reuse is False


class TestBuildPassesReuse:
    """Test that build() passes reuse parameter to get_logger()."""

    def test_build_passes_reuse_false_to_get_logger(self) -> None:
        """build() should pass reuse=False to get_logger when configured."""
        with patch("fapilog.get_logger") as mock_get_logger:
            mock_get_logger.return_value = "fake_logger"
            LoggerBuilder().add_stdout().reuse(False).build()
            mock_get_logger.assert_called_once()
            call_kwargs = mock_get_logger.call_args.kwargs
            assert call_kwargs["reuse"] is False

    def test_build_passes_reuse_true_by_default(self) -> None:
        """build() should pass reuse=True by default."""
        with patch("fapilog.get_logger") as mock_get_logger:
            mock_get_logger.return_value = "fake_logger"
            LoggerBuilder().add_stdout().build()
            mock_get_logger.assert_called_once()
            call_kwargs = mock_get_logger.call_args.kwargs
            assert call_kwargs["reuse"] is True


class TestBuildAsyncPassesReuse:
    """Test that build_async() passes reuse parameter to get_async_logger()."""

    @pytest.mark.asyncio
    async def test_build_async_passes_reuse_false(self) -> None:
        """build_async() should pass reuse=False to get_async_logger."""
        with patch("fapilog.get_async_logger", new_callable=AsyncMock) as mock:
            mock.return_value = "fake_logger"
            await AsyncLoggerBuilder().add_stdout().reuse(False).build_async()
            mock.assert_called_once()
            call_kwargs = mock.call_args.kwargs
            assert call_kwargs["reuse"] is False

    @pytest.mark.asyncio
    async def test_build_async_passes_reuse_true_by_default(self) -> None:
        """build_async() should pass reuse=True by default."""
        with patch("fapilog.get_async_logger", new_callable=AsyncMock) as mock:
            mock.return_value = "fake_logger"
            await AsyncLoggerBuilder().add_stdout().build_async()
            mock.assert_called_once()
            call_kwargs = mock.call_args.kwargs
            assert call_kwargs["reuse"] is True
