"""
Tests for LoggingMiddleware to improve coverage.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("fastapi")

from fapilog.fastapi.logging import LoggingMiddleware


class TestLoggingMiddleware:
    """Tests for LoggingMiddleware."""

    def test_init_defaults(self) -> None:
        """Test middleware initialization with defaults."""
        app = MagicMock()
        middleware = LoggingMiddleware(app)

        assert middleware._logger is None
        assert middleware._skip_paths == set()
        assert middleware._sample_rate == 1.0
        assert middleware._include_headers is False
        assert middleware._redact_headers == set()

    def test_init_with_options(self) -> None:
        """Test middleware initialization with options."""
        app = MagicMock()
        middleware = LoggingMiddleware(
            app,
            skip_paths=["/health", "/metrics"],
            sample_rate=0.5,
            include_headers=True,
            redact_headers=["Authorization", "Cookie"],
        )

        assert middleware._skip_paths == {"/health", "/metrics"}
        assert middleware._sample_rate == 0.5
        assert middleware._include_headers is True
        assert middleware._redact_headers == {"authorization", "cookie"}

    def test_init_with_logger(self) -> None:
        """Test middleware initialization with custom logger."""
        app = MagicMock()
        logger = MagicMock()
        middleware = LoggingMiddleware(app, logger=logger)

        assert middleware._logger is logger

    @pytest.mark.asyncio
    async def test_dispatch_skipped_path(self) -> None:
        """Test dispatch skips configured paths."""
        app = MagicMock()
        middleware = LoggingMiddleware(app, skip_paths=["/health"])

        # Create mock request
        request = MagicMock()
        request.url.path = "/health"

        # Create mock response
        response = MagicMock()

        # Create mock call_next
        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(request, call_next)

        assert result is response
        call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_dispatch_normal_request(self) -> None:
        """Test dispatch logs normal requests."""
        app = MagicMock()
        logger = AsyncMock()
        logger.info = AsyncMock()
        middleware = LoggingMiddleware(app, logger=logger)

        # Create mock request
        request = MagicMock()
        request.url.path = "/api/data"
        request.method = "GET"
        request.headers = {"X-Request-ID": "test-123"}
        request.client = MagicMock(host="127.0.0.1")

        # Create mock response
        response = MagicMock()
        response.status_code = 200
        response.headers = {}

        # Create mock call_next
        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(request, call_next)

        assert result is response
        assert "X-Request-ID" in response.headers

    @pytest.mark.asyncio
    async def test_get_logger_lazy_init(self, monkeypatch) -> None:
        """Test _get_logger creates logger on first call."""
        logger = AsyncMock()

        async def fake_get_async_logger(name: str | None = None, *, preset=None):
            return logger

        monkeypatch.setattr("fapilog.get_async_logger", fake_get_async_logger)
        middleware = LoggingMiddleware(MagicMock())
        request = MagicMock()
        request.app = SimpleNamespace(state=SimpleNamespace())

        result = await middleware._get_logger(request)

        assert result is logger
        assert middleware._logger is logger

    @pytest.mark.asyncio
    async def test_get_logger_prefers_app_state(self) -> None:
        """Test _get_logger uses app state logger when available."""
        app = SimpleNamespace(state=SimpleNamespace())
        logger = AsyncMock()
        app.state.fapilog_logger = logger
        middleware = LoggingMiddleware(MagicMock())
        request = MagicMock()
        request.app = app

        result = await middleware._get_logger(request)

        assert result is logger

    @pytest.mark.asyncio
    async def test_get_logger_prefers_state_map(self) -> None:
        """Test _get_logger reads the starlette State map."""
        logger = AsyncMock()
        app = SimpleNamespace(state=SimpleNamespace(_state={"fapilog_logger": logger}))
        middleware = LoggingMiddleware(MagicMock())
        request = MagicMock()
        request.app = app

        result = await middleware._get_logger(request)

        assert result is logger

    @pytest.mark.asyncio
    async def test_get_logger_falls_back_to_async_logger(self, monkeypatch) -> None:
        """Test _get_logger falls back to get_async_logger when needed."""
        logger = AsyncMock()
        get_async_logger = AsyncMock(return_value=logger)

        monkeypatch.setattr("fapilog.get_async_logger", get_async_logger)
        middleware = LoggingMiddleware(MagicMock())
        request = MagicMock()
        request.app = SimpleNamespace(state=SimpleNamespace())

        result = await middleware._get_logger(request)
        second = await middleware._get_logger(request)

        assert result is logger
        assert second is logger
        get_async_logger.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_log_completion_with_headers(self) -> None:
        """Test _log_completion includes headers when configured."""
        app = MagicMock()
        logger = AsyncMock()
        logger.info = AsyncMock()
        middleware = LoggingMiddleware(
            app,
            logger=logger,
            include_headers=True,
            redact_headers=["authorization"],
        )

        # Create mock request
        request = MagicMock()
        request.url.path = "/api/data"
        request.method = "GET"
        request.headers = {
            "authorization": "Bearer secret",
            "content-type": "application/json",
        }
        request.client = MagicMock(host="127.0.0.1")

        await middleware._log_completion(
            request=request,
            status_code=200,
            correlation_id="test-123",
            latency_ms=10.5,
        )

        logger.info.assert_called_once()
        call_args = logger.info.call_args
        # Headers should be passed with redaction
        headers = call_args.kwargs["headers"]
        assert headers["authorization"] == "***"
        assert headers["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_log_completion_with_sampling(self) -> None:
        """Test _log_completion respects sample rate."""
        app = MagicMock()
        logger = AsyncMock()
        logger.info = AsyncMock()
        middleware = LoggingMiddleware(app, logger=logger, sample_rate=0.0)

        # Create mock request
        request = MagicMock()
        request.url.path = "/api/data"

        # With sample_rate=0.0, should not log
        await middleware._log_completion(
            request=request,
            status_code=200,
            correlation_id="test-123",
            latency_ms=10.5,
        )

        # Logger should not be called due to sampling
        logger.info.assert_not_called()

    @pytest.mark.asyncio
    async def test_log_error_uses_logger(self) -> None:
        """Test _log_error uses the injected logger."""
        app = MagicMock()
        logger = AsyncMock()
        logger.error = AsyncMock()
        middleware = LoggingMiddleware(app, logger=logger)

        request = MagicMock()
        request.app = SimpleNamespace(state=SimpleNamespace())
        request.method = "GET"
        request.url.path = "/boom"

        await middleware._log_error(
            request=request,
            status_code=500,
            correlation_id="cid-1",
            latency_ms=10.0,
            exc=RuntimeError("boom"),
        )

        logger.error.assert_called_once()
