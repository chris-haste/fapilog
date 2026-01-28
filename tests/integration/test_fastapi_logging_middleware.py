import asyncio
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from fapilog.fastapi.context import RequestContextMiddleware
from fapilog.fastapi.logging import LoggingMiddleware

pytestmark = pytest.mark.integration


class _StubAsyncLogger:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def info(self, message: str, **metadata: Any) -> None:
        self.events.append({"level": "INFO", "message": message, "metadata": metadata})

    async def error(self, message: str, **metadata: Any) -> None:
        self.events.append({"level": "ERROR", "message": message, "metadata": metadata})


def _make_app(
    logger: _StubAsyncLogger,
    *,
    skip_paths: list[str] | None = None,
    log_errors_on_skip: bool = True,
) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        LoggingMiddleware,
        logger=logger,
        skip_paths=skip_paths or [],
        log_errors_on_skip=log_errors_on_skip,
    )

    @app.get("/ok")
    async def ok() -> dict[str, str]:
        await asyncio.sleep(0)  # ensure async path
        return {"ok": "yes"}

    @app.get("/fail")
    async def fail() -> dict[str, str]:
        raise HTTPException(status_code=418, detail="boom")

    @app.get("/boom")
    async def boom() -> dict[str, str]:
        raise RuntimeError("crash")

    return app


def test_logging_middleware_records_success():
    logger = _StubAsyncLogger()
    app = _make_app(logger)
    client = TestClient(app)

    resp = client.get("/ok")
    assert resp.status_code == 200

    assert any(
        e["message"] == "request_completed"
        and e["metadata"].get("status_code") == 200
        and e["metadata"].get("path") == "/ok"
        for e in logger.events
    )


def test_logging_middleware_records_http_exception():
    logger = _StubAsyncLogger()
    app = _make_app(logger)
    client = TestClient(app)

    resp = client.get("/fail")
    assert resp.status_code == 418

    assert any(
        e["message"] == "request_completed"
        and e["metadata"].get("status_code") == 418
        and e["metadata"].get("path") == "/fail"
        for e in logger.events
    )


def test_logging_middleware_records_uncaught_exception():
    logger = _StubAsyncLogger()
    app = _make_app(logger)
    client = TestClient(app, raise_server_exceptions=False)

    resp = client.get("/boom")
    assert resp.status_code == 500

    assert any(
        e["message"] == "request_failed"
        and e["metadata"].get("status_code") == 500
        and e["metadata"].get("path") == "/boom"
        for e in logger.events
    )


def test_logging_middleware_skips_paths():
    logger = _StubAsyncLogger()
    app = _make_app(logger, skip_paths=["/ok"])
    client = TestClient(app)

    resp = client.get("/ok")
    assert resp.status_code == 200

    assert all(e["metadata"].get("path") != "/ok" for e in logger.events)


def test_logging_middleware_sampling_drops_success(monkeypatch):
    logger = _StubAsyncLogger()
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        LoggingMiddleware,
        logger=logger,
        skip_paths=[],
        sample_rate=0.0,
    )

    @app.get("/ok")
    async def ok() -> dict[str, str]:
        return {"ok": "yes"}

    client = TestClient(app)
    resp = client.get("/ok")
    assert resp.status_code == 200
    assert all(e["message"] != "request_completed" for e in logger.events)


def test_logging_middleware_sampling_keeps_errors(monkeypatch):
    logger = _StubAsyncLogger()
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        LoggingMiddleware,
        logger=logger,
        sample_rate=0.0,
    )

    @app.get("/boom")
    async def boom() -> dict[str, str]:
        raise RuntimeError("crash")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/boom")
    assert resp.status_code == 500

    assert any(e["message"] == "request_failed" for e in logger.events)


def test_logging_middleware_redacts_headers(monkeypatch):
    logger = _StubAsyncLogger()
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        LoggingMiddleware,
        logger=logger,
        include_headers=True,
        redact_headers=["authorization"],
    )

    @app.get("/ok")
    async def ok() -> dict[str, str]:
        return {"ok": "yes"}

    client = TestClient(app)
    resp = client.get("/ok", headers={"Authorization": "secret", "X-Test": "keep"})
    assert resp.status_code == 200

    header_events = [e for e in logger.events if e["message"] == "request_completed"]
    assert header_events, "Expected completion log with headers"
    headers = header_events[0]["metadata"].get("headers", {})
    assert headers.get("authorization") == "***"
    assert headers.get("x-test") == "keep"


def test_logging_middleware_default_logger_success(monkeypatch):
    events: list[dict[str, Any]] = []

    class DummyLogger:
        async def info(self, message: str, **metadata: Any) -> None:
            events.append({"message": message, "metadata": metadata})

        async def error(self, message: str, **metadata: Any) -> None:
            events.append({"message": message, "metadata": metadata})

    async def fake_get_async_logger(name: str | None = None, *, settings=None):
        return DummyLogger()

    monkeypatch.setattr("fapilog.get_async_logger", fake_get_async_logger)

    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(LoggingMiddleware)  # no logger provided

    @app.get("/ok")
    async def ok() -> dict[str, str]:
        return {"ok": "yes"}

    client = TestClient(app)
    resp = client.get("/ok", headers={"X-Request-ID": "rid-123"})
    assert resp.status_code == 200
    assert resp.headers["X-Request-ID"] == "rid-123"
    assert any(e["message"] == "request_completed" for e in events)


def test_logging_middleware_default_logger_error(monkeypatch):
    events: list[dict[str, Any]] = []

    class DummyLogger:
        async def info(self, message: str, **metadata: Any) -> None:
            events.append({"message": message, "metadata": metadata})

        async def error(self, message: str, **metadata: Any) -> None:
            events.append({"message": message, "metadata": metadata})

    async def fake_get_async_logger(name: str | None = None, *, settings=None):
        return DummyLogger()

    monkeypatch.setattr("fapilog.get_async_logger", fake_get_async_logger)

    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(LoggingMiddleware)  # no logger provided

    @app.get("/boom")
    async def boom() -> dict[str, str]:
        raise RuntimeError("crash")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/boom")
    assert resp.status_code == 500
    assert any(e["message"] == "request_failed" for e in events)


class TestLogErrorsOnSkip:
    """Integration tests for log_errors_on_skip feature (Story 1.32)."""

    def test_health_endpoint_error_logged(self):
        """Test that errors on skipped health endpoints are logged by default."""
        logger = _StubAsyncLogger()
        app = _make_app(logger, skip_paths=["/health"])

        @app.get("/health")
        async def health() -> dict[str, str]:
            raise RuntimeError("Database connection failed")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")

        assert resp.status_code == 500
        # Error should be logged despite path being skipped
        error_events = [e for e in logger.events if e["message"] == "request_failed"]
        assert len(error_events) == 1
        assert error_events[0]["metadata"]["path"] == "/health"
        assert error_events[0]["metadata"]["error_type"] == "RuntimeError"

    def test_health_endpoint_success_silent(self):
        """Test that successful requests on skipped health endpoints are not logged."""
        logger = _StubAsyncLogger()
        app = _make_app(logger, skip_paths=["/health"])

        @app.get("/health")
        async def health() -> dict[str, str]:
            return {"status": "ok"}

        client = TestClient(app)
        resp = client.get("/health")

        assert resp.status_code == 200
        # No log entries for successful health check
        assert all(e["metadata"].get("path") != "/health" for e in logger.events)

    def test_log_errors_on_skip_false_silences_errors(self):
        """Test that log_errors_on_skip=False completely silences skipped paths."""
        logger = _StubAsyncLogger()
        app = _make_app(logger, skip_paths=["/health"], log_errors_on_skip=False)

        @app.get("/health")
        async def health() -> dict[str, str]:
            raise RuntimeError("Database connection failed")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")

        assert resp.status_code == 500
        # No log entries at all for /health
        assert all(e["metadata"].get("path") != "/health" for e in logger.events)

    def test_http_exception_on_skipped_path_not_logged(self):
        """HTTPExceptions on skipped paths are not logged (handled by FastAPI exception handler)."""
        # Note: HTTPExceptions are caught by FastAPI's exception handler and converted
        # to responses before reaching the middleware's exception handler. This is
        # expected behavior since HTTPExceptions are controlled error responses,
        # not unexpected failures.
        logger = _StubAsyncLogger()
        app = _make_app(logger, skip_paths=["/health"])

        @app.get("/health")
        async def health() -> dict[str, str]:
            raise HTTPException(status_code=503, detail="Service unavailable")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")

        assert resp.status_code == 503
        # HTTPExceptions are handled by FastAPI, not logged as errors on skipped paths
        assert all(e["metadata"].get("path") != "/health" for e in logger.events)


class TestRequireLogger:
    """Integration tests for require_logger feature (Story 12.24)."""

    def test_require_logger_raises_without_state(self):
        """require_logger=True raises RuntimeError if no logger in app.state."""
        app = FastAPI()
        app.add_middleware(LoggingMiddleware, require_logger=True)

        @app.get("/ok")
        async def ok() -> dict[str, str]:
            return {"ok": "yes"}

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/ok")

        # Expect 500 because middleware raises RuntimeError
        assert resp.status_code == 500

    def test_require_logger_works_with_injected_logger(self):
        """require_logger=True works when logger is passed directly."""
        logger = _StubAsyncLogger()
        app = FastAPI()
        app.add_middleware(LoggingMiddleware, logger=logger, require_logger=True)

        @app.get("/ok")
        async def ok() -> dict[str, str]:
            return {"ok": "yes"}

        client = TestClient(app)
        resp = client.get("/ok")

        assert resp.status_code == 200
        assert any(
            e["message"] == "request_completed" and e["metadata"].get("path") == "/ok"
            for e in logger.events
        )

    def test_require_logger_works_with_app_state(self):
        """require_logger=True works when logger is in app.state."""
        logger = _StubAsyncLogger()
        app = FastAPI()
        app.state.fapilog_logger = logger
        app.add_middleware(LoggingMiddleware, require_logger=True)

        @app.get("/ok")
        async def ok() -> dict[str, str]:
            return {"ok": "yes"}

        client = TestClient(app)
        resp = client.get("/ok")

        assert resp.status_code == 200
        assert any(
            e["message"] == "request_completed" and e["metadata"].get("path") == "/ok"
            for e in logger.events
        )

    def test_default_lazy_creation_preserved(self, monkeypatch):
        """Default behavior (require_logger=False) preserves lazy creation."""
        events: list[dict[str, Any]] = []

        class DummyLogger:
            async def info(self, message: str, **metadata: Any) -> None:
                events.append({"message": message, "metadata": metadata})

            async def error(self, message: str, **metadata: Any) -> None:
                events.append({"message": message, "metadata": metadata})

        async def fake_get_async_logger(name: str | None = None, *, settings=None):
            return DummyLogger()

        monkeypatch.setattr("fapilog.get_async_logger", fake_get_async_logger)

        app = FastAPI()
        # require_logger defaults to False - lazy creation still works
        app.add_middleware(LoggingMiddleware)

        @app.get("/ok")
        async def ok() -> dict[str, str]:
            return {"ok": "yes"}

        client = TestClient(app)
        resp = client.get("/ok")

        assert resp.status_code == 200
        assert any(e["message"] == "request_completed" for e in events)

    def test_error_message_helpful(self):
        """Error message includes clear instructions for fixing the issue."""
        import pytest

        app = FastAPI()
        app.add_middleware(LoggingMiddleware, require_logger=True)

        @app.get("/ok")
        async def ok() -> dict[str, str]:
            return {"ok": "yes"}

        client = TestClient(app, raise_server_exceptions=True)
        with pytest.raises(RuntimeError) as exc_info:
            client.get("/ok")

        error_msg = str(exc_info.value)
        # Error message should explain what's missing and how to fix it
        assert "app.state" in error_msg
        assert "setup_logging" in error_msg
        assert "logger=" in error_msg
