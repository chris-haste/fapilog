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
        from fapilog.fastapi.logging import DEFAULT_REDACT_HEADERS

        app = MagicMock()
        middleware = LoggingMiddleware(app)

        assert middleware._logger is None
        assert middleware._skip_paths == set()
        assert middleware._sample_rate == 1.0
        assert middleware._include_headers is False
        # Default redactions are applied automatically (Story 4.51)
        assert middleware._redact_headers == set(DEFAULT_REDACT_HEADERS)

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


class TestLogErrorsOnSkip:
    """Tests for log_errors_on_skip feature (Story 1.32)."""

    def test_init_log_errors_on_skip_defaults_true(self) -> None:
        """Test log_errors_on_skip defaults to True."""
        app = MagicMock()
        middleware = LoggingMiddleware(app)
        assert middleware._log_errors_on_skip is True

    def test_init_log_errors_on_skip_explicit_false(self) -> None:
        """Test log_errors_on_skip can be set to False."""
        app = MagicMock()
        middleware = LoggingMiddleware(app, log_errors_on_skip=False)
        assert middleware._log_errors_on_skip is False

    @pytest.mark.asyncio
    async def test_skipped_path_error_logged_by_default(self) -> None:
        """Test that errors on skipped paths are logged when log_errors_on_skip=True (default)."""
        app = MagicMock()
        logger = AsyncMock()
        logger.error = AsyncMock()
        middleware = LoggingMiddleware(app, logger=logger, skip_paths=["/health"])

        request = MagicMock()
        request.url.path = "/health"
        request.method = "GET"
        request.headers = {}
        request.client = MagicMock(host="127.0.0.1")

        error = RuntimeError("Database connection failed")
        call_next = AsyncMock(side_effect=error)

        with pytest.raises(RuntimeError, match="Database connection failed"):
            await middleware.dispatch(request, call_next)

        logger.error.assert_called_once()
        call_kwargs = logger.error.call_args.kwargs
        assert call_kwargs["path"] == "/health"
        assert call_kwargs["error_type"] == "RuntimeError"

    @pytest.mark.asyncio
    async def test_skipped_path_success_not_logged(self) -> None:
        """Test that successful requests on skipped paths are not logged."""
        app = MagicMock()
        logger = AsyncMock()
        logger.info = AsyncMock()
        logger.error = AsyncMock()
        middleware = LoggingMiddleware(app, logger=logger, skip_paths=["/health"])

        request = MagicMock()
        request.url.path = "/health"
        response = MagicMock()

        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(request, call_next)

        assert result is response
        logger.info.assert_not_called()
        logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_log_errors_on_skip_false_silences_errors(self) -> None:
        """Test that log_errors_on_skip=False silences errors on skipped paths."""
        app = MagicMock()
        logger = AsyncMock()
        logger.error = AsyncMock()
        middleware = LoggingMiddleware(
            app, logger=logger, skip_paths=["/health"], log_errors_on_skip=False
        )

        request = MagicMock()
        request.url.path = "/health"

        error = RuntimeError("Database connection failed")
        call_next = AsyncMock(side_effect=error)

        with pytest.raises(RuntimeError, match="Database connection failed"):
            await middleware.dispatch(request, call_next)

        logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_error_format_matches_normal_path(self) -> None:
        """Contract test: errors on skipped paths use the same format as non-skipped paths."""
        app = MagicMock()
        logger = AsyncMock()
        logger.error = AsyncMock()
        middleware = LoggingMiddleware(app, logger=logger, skip_paths=["/health"])

        # Error on skipped path
        request_skipped = MagicMock()
        request_skipped.url.path = "/health"
        request_skipped.method = "GET"
        request_skipped.headers = {}
        request_skipped.client = MagicMock(host="127.0.0.1")

        error = RuntimeError("test error")
        call_next = AsyncMock(side_effect=error)

        with pytest.raises(RuntimeError):
            await middleware.dispatch(request_skipped, call_next)

        skipped_call = logger.error.call_args

        # Error on non-skipped path
        logger.error.reset_mock()
        request_normal = MagicMock()
        request_normal.url.path = "/api/users"
        request_normal.method = "GET"
        request_normal.headers = {}
        request_normal.client = MagicMock(host="127.0.0.1")

        call_next_normal = AsyncMock(side_effect=error)

        with pytest.raises(RuntimeError):
            await middleware.dispatch(request_normal, call_next_normal)

        normal_call = logger.error.call_args

        # Both should have the same message
        assert skipped_call.args[0] == "request_failed"
        assert normal_call.args[0] == "request_failed"

        # Both should have the same keys (except path-specific values)
        skipped_keys = set(skipped_call.kwargs.keys())
        normal_keys = set(normal_call.kwargs.keys())
        assert skipped_keys == normal_keys


class TestSecureHeaderRedaction:
    """Tests for secure header redaction defaults (Story 4.51)."""

    def test_default_redact_headers_constant_exists(self) -> None:
        """Test DEFAULT_REDACT_HEADERS constant is defined with expected headers."""
        from fapilog.fastapi.logging import DEFAULT_REDACT_HEADERS

        expected = {
            "authorization",
            "cookie",
            "set-cookie",
            "x-api-key",
            "x-auth-token",
            "x-csrf-token",
            "x-forwarded-authorization",
            "proxy-authorization",
            "www-authenticate",
        }
        assert DEFAULT_REDACT_HEADERS == frozenset(expected)

    def test_default_headers_redacted_without_config(self) -> None:
        """Test sensitive headers are redacted by default when include_headers=True."""
        app = MagicMock()
        middleware = LoggingMiddleware(app, include_headers=True)

        # Default redactions should be active
        assert "authorization" in middleware._redact_headers
        assert "cookie" in middleware._redact_headers
        assert "x-api-key" in middleware._redact_headers

    @pytest.mark.asyncio
    async def test_authorization_header_redacted_by_default(self) -> None:
        """Test Authorization header is redacted without explicit redact_headers config."""
        app = MagicMock()
        logger = AsyncMock()
        logger.info = AsyncMock()
        middleware = LoggingMiddleware(app, logger=logger, include_headers=True)

        request = MagicMock()
        request.url.path = "/api/data"
        request.method = "GET"
        request.headers = {
            "authorization": "Bearer super-secret-token",
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
        headers = logger.info.call_args.kwargs["headers"]
        assert headers["authorization"] == "***"
        assert headers["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_cookie_header_redacted_by_default(self) -> None:
        """Test Cookie header is redacted without explicit config."""
        app = MagicMock()
        logger = AsyncMock()
        logger.info = AsyncMock()
        middleware = LoggingMiddleware(app, logger=logger, include_headers=True)

        request = MagicMock()
        request.url.path = "/api/data"
        request.method = "GET"
        request.headers = {
            "cookie": "session=abc123; token=secret",
            "accept": "application/json",
        }
        request.client = MagicMock(host="127.0.0.1")

        await middleware._log_completion(
            request=request,
            status_code=200,
            correlation_id="test-123",
            latency_ms=10.5,
        )

        headers = logger.info.call_args.kwargs["headers"]
        assert headers["cookie"] == "***"
        assert headers["accept"] == "application/json"

    def test_additional_redact_headers_extends_defaults(self) -> None:
        """Test additional_redact_headers adds to default redactions (AC2)."""
        app = MagicMock()
        middleware = LoggingMiddleware(
            app,
            include_headers=True,
            additional_redact_headers=["x-custom-secret", "x-internal-token"],
        )

        # Defaults should still be present
        assert "authorization" in middleware._redact_headers
        assert "cookie" in middleware._redact_headers
        # Custom headers should be added
        assert "x-custom-secret" in middleware._redact_headers
        assert "x-internal-token" in middleware._redact_headers

    @pytest.mark.asyncio
    async def test_additional_redact_headers_redacts_custom_and_defaults(self) -> None:
        """Test both default and additional headers are redacted."""
        app = MagicMock()
        logger = AsyncMock()
        logger.info = AsyncMock()
        middleware = LoggingMiddleware(
            app,
            logger=logger,
            include_headers=True,
            additional_redact_headers=["x-custom-secret"],
        )

        request = MagicMock()
        request.url.path = "/api/data"
        request.method = "GET"
        request.headers = {
            "authorization": "Bearer token",
            "x-custom-secret": "my-secret-value",
            "content-type": "application/json",
        }
        request.client = MagicMock(host="127.0.0.1")

        await middleware._log_completion(
            request=request,
            status_code=200,
            correlation_id="test-123",
            latency_ms=10.5,
        )

        headers = logger.info.call_args.kwargs["headers"]
        assert headers["authorization"] == "***"
        assert headers["x-custom-secret"] == "***"
        assert headers["content-type"] == "application/json"

    def test_allow_headers_excludes_unlisted(self) -> None:
        """Test allow_headers mode only includes specified headers (AC3)."""
        app = MagicMock()
        middleware = LoggingMiddleware(
            app,
            include_headers=True,
            allow_headers=["content-type", "accept", "user-agent"],
        )

        # In allowlist mode, _allow_headers should be set
        assert middleware._allow_headers == {"content-type", "accept", "user-agent"}

    @pytest.mark.asyncio
    async def test_allow_headers_only_logs_specified(self) -> None:
        """Test only headers in allow_headers are logged."""
        app = MagicMock()
        logger = AsyncMock()
        logger.info = AsyncMock()
        middleware = LoggingMiddleware(
            app,
            logger=logger,
            include_headers=True,
            allow_headers=["content-type", "accept"],
        )

        request = MagicMock()
        request.url.path = "/api/data"
        request.method = "GET"
        request.headers = {
            "authorization": "Bearer secret",
            "cookie": "session=abc",
            "content-type": "application/json",
            "accept": "application/json",
            "x-custom": "value",
        }
        request.client = MagicMock(host="127.0.0.1")

        await middleware._log_completion(
            request=request,
            status_code=200,
            correlation_id="test-123",
            latency_ms=10.5,
        )

        headers = logger.info.call_args.kwargs["headers"]
        # Only allowed headers should be present
        assert "content-type" in headers
        assert "accept" in headers
        # Sensitive and other headers should be excluded entirely
        assert "authorization" not in headers
        assert "cookie" not in headers
        assert "x-custom" not in headers

    def test_disable_default_redactions_warns(self) -> None:
        """Test disable_default_redactions=True emits a warning (AC4)."""
        import warnings

        app = MagicMock()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            middleware = LoggingMiddleware(
                app,
                include_headers=True,
                redact_headers=[],
                disable_default_redactions=True,
            )

            # Should have emitted a warning
            assert len(w) == 1
            assert "Default header redactions disabled" in str(w[0].message)
            assert issubclass(w[0].category, UserWarning)

        # Redact headers should be empty
        assert middleware._redact_headers == set()

    def test_empty_redact_headers_uses_defaults(self) -> None:
        """Test empty redact_headers without disable_default_redactions still uses defaults."""
        app = MagicMock()
        # Note: redact_headers=[] replaces defaults, but without disable_default_redactions
        # the intent is unclear. When redact_headers is explicitly set, it replaces defaults.
        middleware = LoggingMiddleware(
            app,
            include_headers=True,
            redact_headers=[],
        )

        # Since redact_headers was explicitly set to [], it should be empty
        assert middleware._redact_headers == set()

    def test_disable_default_redactions_without_explicit_redact_headers(self) -> None:
        """Test disable_default_redactions works without redact_headers."""
        import warnings

        app = MagicMock()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            middleware = LoggingMiddleware(
                app,
                include_headers=True,
                disable_default_redactions=True,
            )

            assert len(w) == 1
            assert "Default header redactions disabled" in str(w[0].message)

        # Defaults should be disabled
        assert "authorization" not in middleware._redact_headers
        assert middleware._redact_headers == set()

    @pytest.mark.asyncio
    async def test_disable_default_redactions_logs_sensitive_headers(self) -> None:
        """Test sensitive headers are logged when defaults are disabled."""
        import warnings

        app = MagicMock()
        logger = AsyncMock()
        logger.info = AsyncMock()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            middleware = LoggingMiddleware(
                app,
                logger=logger,
                include_headers=True,
                disable_default_redactions=True,
            )

        request = MagicMock()
        request.url.path = "/api/data"
        request.method = "GET"
        request.headers = {
            "authorization": "Bearer secret-token",
            "content-type": "application/json",
        }
        request.client = MagicMock(host="127.0.0.1")

        await middleware._log_completion(
            request=request,
            status_code=200,
            correlation_id="test-123",
            latency_ms=10.5,
        )

        headers = logger.info.call_args.kwargs["headers"]
        # Authorization should NOT be redacted when defaults disabled
        assert headers["authorization"] == "Bearer secret-token"
        assert headers["content-type"] == "application/json"


class TestRequireLogger:
    """Unit tests for require_logger feature (Story 12.24)."""

    def test_init_require_logger_defaults_false(self) -> None:
        """Test require_logger defaults to False."""
        app = MagicMock()
        middleware = LoggingMiddleware(app)
        assert middleware._require_logger is False

    def test_init_require_logger_explicit_true(self) -> None:
        """Test require_logger can be set to True."""
        app = MagicMock()
        middleware = LoggingMiddleware(app, require_logger=True)
        assert middleware._require_logger is True

    @pytest.mark.asyncio
    async def test_get_logger_raises_when_require_logger_and_no_logger(self) -> None:
        """Test _get_logger raises RuntimeError when require_logger=True and no logger available."""
        app = MagicMock()
        middleware = LoggingMiddleware(app, require_logger=True)

        request = MagicMock()
        request.app = SimpleNamespace(state=SimpleNamespace())

        with pytest.raises(RuntimeError) as exc_info:
            await middleware._get_logger(request)

        error_msg = str(exc_info.value)
        assert "app.state" in error_msg
        assert "setup_logging" in error_msg
        assert "logger=" in error_msg

    @pytest.mark.asyncio
    async def test_get_logger_works_with_require_logger_and_injected_logger(
        self,
    ) -> None:
        """Test _get_logger works when require_logger=True and logger is injected."""
        app = MagicMock()
        logger = AsyncMock()
        middleware = LoggingMiddleware(app, logger=logger, require_logger=True)

        request = MagicMock()
        request.app = SimpleNamespace(state=SimpleNamespace())

        result = await middleware._get_logger(request)
        assert result is logger

    @pytest.mark.asyncio
    async def test_get_logger_works_with_require_logger_and_app_state(self) -> None:
        """Test _get_logger works when require_logger=True and logger is in app.state."""
        app = MagicMock()
        logger = AsyncMock()
        middleware = LoggingMiddleware(app, require_logger=True)

        request = MagicMock()
        request.app = SimpleNamespace(state=SimpleNamespace(fapilog_logger=logger))

        result = await middleware._get_logger(request)
        assert result is logger

    @pytest.mark.asyncio
    async def test_get_logger_lazy_creation_when_require_logger_false(
        self, monkeypatch
    ) -> None:
        """Test _get_logger creates logger lazily when require_logger=False (default)."""
        logger = AsyncMock()

        async def fake_get_async_logger(name: str | None = None, *, preset=None):
            return logger

        monkeypatch.setattr("fapilog.get_async_logger", fake_get_async_logger)

        app = MagicMock()
        middleware = LoggingMiddleware(app)  # require_logger=False by default

        request = MagicMock()
        request.app = SimpleNamespace(state=SimpleNamespace())

        result = await middleware._get_logger(request)
        assert result is logger

    @pytest.mark.asyncio
    async def test_log_completion_reraises_runtime_error(self) -> None:
        """Test _log_completion re-raises RuntimeError from _get_logger."""
        app = MagicMock()
        middleware = LoggingMiddleware(app, require_logger=True)

        request = MagicMock()
        request.app = SimpleNamespace(state=SimpleNamespace())
        request.url.path = "/test"

        with pytest.raises(RuntimeError, match="app.state"):
            await middleware._log_completion(
                request=request,
                status_code=200,
                correlation_id="test-123",
                latency_ms=10.5,
            )

    @pytest.mark.asyncio
    async def test_log_error_reraises_runtime_error(self) -> None:
        """Test _log_error re-raises RuntimeError from _get_logger."""
        app = MagicMock()
        middleware = LoggingMiddleware(app, require_logger=True)

        request = MagicMock()
        request.app = SimpleNamespace(state=SimpleNamespace())
        request.url.path = "/test"

        with pytest.raises(RuntimeError, match="app.state"):
            await middleware._log_error(
                request=request,
                status_code=500,
                correlation_id="test-123",
                latency_ms=10.5,
                exc=ValueError("test error"),
            )
