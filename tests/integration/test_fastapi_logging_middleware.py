import asyncio
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from fapilog.fastapi.context import RequestContextMiddleware
from fapilog.fastapi.logging import LoggingMiddleware


class _StubAsyncLogger:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def info(self, message: str, **metadata: Any) -> None:
        self.events.append({"level": "INFO", "message": message, "metadata": metadata})

    async def error(self, message: str, **metadata: Any) -> None:
        self.events.append({"level": "ERROR", "message": message, "metadata": metadata})


def _make_app(
    logger: _StubAsyncLogger, *, skip_paths: list[str] | None = None
) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        LoggingMiddleware,
        logger=logger,
        skip_paths=skip_paths or [],
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
