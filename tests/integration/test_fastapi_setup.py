from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from fapilog.fastapi import get_request_logger, setup_logging

pytestmark = pytest.mark.integration


def test_setup_logging_creates_logger_and_drains(monkeypatch) -> None:
    events: list[str] = []

    class DummyLogger:
        async def drain(self) -> None:
            events.append("drain")

    logger = DummyLogger()

    async def fake_get_async_logger(name: str | None = None, *, preset=None):
        events.append(f"created:{name}:{preset}")
        return logger

    monkeypatch.setattr("fapilog.get_async_logger", fake_get_async_logger)

    app = FastAPI(lifespan=setup_logging(preset="fastapi"))

    with TestClient(app):
        assert app.state.fapilog_logger is logger
        assert "created:fastapi:fastapi" in events

    assert "drain" in events


def test_setup_logging_wraps_user_lifespan_order(monkeypatch) -> None:
    events: list[str] = []

    class DummyLogger:
        async def drain(self) -> None:
            events.append("fapilog_drain")

    async def fake_get_async_logger(name: str | None = None, *, preset=None):
        events.append("fapilog_start")
        return DummyLogger()

    monkeypatch.setattr("fapilog.get_async_logger", fake_get_async_logger)

    @asynccontextmanager
    async def user_lifespan(app: FastAPI):
        assert hasattr(app.state, "fapilog_logger")
        events.append("user_start")
        yield
        events.append("user_shutdown")

    app = FastAPI(lifespan=setup_logging(wrap_lifespan=user_lifespan))

    with TestClient(app):
        pass

    assert events == [
        "fapilog_start",
        "user_start",
        "user_shutdown",
        "fapilog_drain",
    ]


def test_setup_logging_adds_middleware_when_app_provided(monkeypatch) -> None:
    class DummyLogger:
        async def drain(self) -> None:
            return None

    logger = DummyLogger()

    async def fake_get_async_logger(name: str | None = None, *, preset=None):
        return logger

    monkeypatch.setattr("fapilog.get_async_logger", fake_get_async_logger)

    app = FastAPI()
    lifespan = setup_logging(
        app,
        skip_paths=["/health"],
        sample_rate=0.25,
        redact_headers=["authorization"],
    )

    assert callable(lifespan)

    app.router.lifespan_context = lifespan

    with TestClient(app):
        pass

    middleware = [m.cls.__name__ for m in app.user_middleware]
    assert middleware[0] == "RequestContextMiddleware"
    assert middleware[1] == "LoggingMiddleware"

    logging_mw = next(
        mw for mw in app.user_middleware if mw.cls.__name__ == "LoggingMiddleware"
    )
    assert logging_mw.kwargs["skip_paths"] == ["/health"]
    assert logging_mw.kwargs["sample_rate"] == 0.25
    assert logging_mw.kwargs["redact_headers"] == ["authorization"]
    assert logging_mw.kwargs["logger"] is logger


def test_setup_logging_adds_middleware_without_app(monkeypatch) -> None:
    class DummyLogger:
        async def drain(self) -> None:
            return None

    logger = DummyLogger()

    async def fake_get_async_logger(name: str | None = None, *, preset=None):
        return logger

    monkeypatch.setattr("fapilog.get_async_logger", fake_get_async_logger)

    app = FastAPI(lifespan=setup_logging())

    with TestClient(app):
        pass

    middleware = [m.cls.__name__ for m in app.user_middleware]
    assert middleware[0] == "RequestContextMiddleware"
    assert middleware[1] == "LoggingMiddleware"


def test_setup_logging_allows_disabling_auto_middleware(monkeypatch) -> None:
    class DummyLogger:
        async def drain(self) -> None:
            return None

    async def fake_get_async_logger(name: str | None = None, *, preset=None):
        return DummyLogger()

    monkeypatch.setattr("fapilog.get_async_logger", fake_get_async_logger)

    app = FastAPI(lifespan=setup_logging(auto_middleware=False))

    with TestClient(app):
        pass

    assert all(
        mw.cls.__name__ not in ("RequestContextMiddleware", "LoggingMiddleware")
        for mw in app.user_middleware
    )


@pytest.mark.asyncio
async def test_get_request_logger_uses_app_state(monkeypatch) -> None:
    class DummyLogger:
        async def drain(self) -> None:
            return None

    logger = DummyLogger()

    async def fake_get_async_logger(name: str | None = None, *, preset=None):
        return logger

    monkeypatch.setattr("fapilog.get_async_logger", fake_get_async_logger)

    app = FastAPI(lifespan=setup_logging())

    @app.get("/log")
    async def log_endpoint(log=Depends(get_request_logger)):
        assert log is app.state.fapilog_logger
        return {"ok": True}

    with TestClient(app) as client:
        response = client.get("/log")
        assert response.status_code == 200


def test_middleware_uses_app_logger_for_request(monkeypatch) -> None:
    events: list[str] = []

    class DummyLogger:
        async def info(self, message: str, **metadata) -> None:
            events.append(message)

        async def error(self, message: str, **metadata) -> None:
            events.append(message)

        async def drain(self) -> None:
            events.append("drain")

    async def fake_get_async_logger(name: str | None = None, *, preset=None):
        return DummyLogger()

    monkeypatch.setattr("fapilog.get_async_logger", fake_get_async_logger)

    app = FastAPI(lifespan=setup_logging())

    @app.get("/ok")
    async def ok() -> dict[str, str]:
        return {"ok": "yes"}

    with TestClient(app) as client:
        response = client.get("/ok")
        assert response.status_code == 200

    assert "request_completed" in events
    assert "drain" in events


def test_logger_refreshes_across_lifespan_restarts(monkeypatch) -> None:
    seen: list[str] = []

    class DummyLogger:
        def __init__(self, label: str) -> None:
            self._label = label

        async def info(self, message: str, **metadata) -> None:
            seen.append(f"{self._label}:{message}")

        async def error(self, message: str, **metadata) -> None:
            seen.append(f"{self._label}:{message}")

        async def drain(self) -> None:
            return None

    created: list[DummyLogger] = []

    async def fake_get_async_logger(name: str | None = None, *, preset=None):
        label = f"logger-{len(created)}"
        logger = DummyLogger(label)
        created.append(logger)
        return logger

    monkeypatch.setattr("fapilog.get_async_logger", fake_get_async_logger)

    app = FastAPI(lifespan=setup_logging())

    @app.get("/ok")
    async def ok() -> dict[str, str]:
        return {"ok": "yes"}

    with TestClient(app) as client:
        response = client.get("/ok")
        assert response.status_code == 200

    with TestClient(app) as client:
        response = client.get("/ok")
        assert response.status_code == 200

    assert any(item.startswith("logger-0:request_completed") for item in seen)
    assert any(item.startswith("logger-1:request_completed") for item in seen)


def test_setup_logging_include_headers(monkeypatch) -> None:
    """Test include_headers enables header logging via setup_logging."""
    logged_headers: list[dict[str, str] | None] = []

    class DummyLogger:
        async def info(self, message: str, **metadata) -> None:
            logged_headers.append(metadata.get("headers"))

        async def error(self, message: str, **metadata) -> None:
            return None

        async def drain(self) -> None:
            return None

    async def fake_get_async_logger(name: str | None = None, *, preset=None):
        return DummyLogger()

    monkeypatch.setattr("fapilog.get_async_logger", fake_get_async_logger)

    app = FastAPI(
        lifespan=setup_logging(
            include_headers=True,
        )
    )

    @app.get("/test")
    async def test_endpoint() -> dict[str, str]:
        return {"ok": "yes"}

    with TestClient(app) as client:
        client.get("/test", headers={"X-Custom-Header": "test-value"})

    assert len(logged_headers) == 1
    assert logged_headers[0] is not None  # noqa: WA003 - type guard before value check
    assert logged_headers[0].get("x-custom-header") == "test-value"


def test_setup_logging_additional_redact_headers(monkeypatch) -> None:
    """Test additional_redact_headers adds custom headers to redaction."""
    logged_headers: list[dict[str, str] | None] = []

    class DummyLogger:
        async def info(self, message: str, **metadata) -> None:
            logged_headers.append(metadata.get("headers"))

        async def error(self, message: str, **metadata) -> None:
            return None

        async def drain(self) -> None:
            return None

    async def fake_get_async_logger(name: str | None = None, *, preset=None):
        return DummyLogger()

    monkeypatch.setattr("fapilog.get_async_logger", fake_get_async_logger)

    app = FastAPI(
        lifespan=setup_logging(
            include_headers=True,
            additional_redact_headers=["X-Internal-Token"],
        )
    )

    @app.get("/test")
    async def test_endpoint() -> dict[str, str]:
        return {"ok": "yes"}

    with TestClient(app) as client:
        client.get(
            "/test",
            headers={
                "X-Internal-Token": "secret-value",
                "X-Custom-Header": "visible-value",
            },
        )

    assert len(logged_headers) == 1
    assert logged_headers[0] is not None  # noqa: WA003 - type guard before value check
    # Custom redact header should be redacted
    assert logged_headers[0].get("x-internal-token") == "***"
    # Non-redacted header should be visible
    assert logged_headers[0].get("x-custom-header") == "visible-value"


def test_setup_logging_allow_headers(monkeypatch) -> None:
    """Test allow_headers enables allowlist mode."""
    logged_headers: list[dict[str, str] | None] = []

    class DummyLogger:
        async def info(self, message: str, **metadata) -> None:
            logged_headers.append(metadata.get("headers"))

        async def error(self, message: str, **metadata) -> None:
            return None

        async def drain(self) -> None:
            return None

    async def fake_get_async_logger(name: str | None = None, *, preset=None):
        return DummyLogger()

    monkeypatch.setattr("fapilog.get_async_logger", fake_get_async_logger)

    app = FastAPI(
        lifespan=setup_logging(
            include_headers=True,
            allow_headers=["Content-Type"],
        )
    )

    @app.get("/test")
    async def test_endpoint() -> dict[str, str]:
        return {"ok": "yes"}

    with TestClient(app) as client:
        client.get(
            "/test",
            headers={
                "Content-Type": "application/json",
                "X-Custom-Header": "should-not-appear",
            },
        )

    assert len(logged_headers) == 1
    assert logged_headers[0] is not None  # noqa: WA003 - type guard before value check
    # Only allowlisted header should appear
    assert logged_headers[0].get("content-type") == "application/json"
    # Non-allowlisted header should not appear
    assert "x-custom-header" not in logged_headers[0]


def test_setup_logging_defaults_unchanged(monkeypatch) -> None:
    """Test that defaults remain unchanged - headers NOT logged by default."""
    logged_headers: list[dict[str, str] | None] = []

    class DummyLogger:
        async def info(self, message: str, **metadata) -> None:
            logged_headers.append(metadata.get("headers"))

        async def error(self, message: str, **metadata) -> None:
            return None

        async def drain(self) -> None:
            return None

    async def fake_get_async_logger(name: str | None = None, *, preset=None):
        return DummyLogger()

    monkeypatch.setattr("fapilog.get_async_logger", fake_get_async_logger)

    app = FastAPI(lifespan=setup_logging(preset="fastapi"))

    @app.get("/test")
    async def test_endpoint() -> dict[str, str]:
        return {"ok": "yes"}

    with TestClient(app) as client:
        client.get("/test", headers={"X-Custom-Header": "test-value"})

    assert len(logged_headers) == 1
    # Headers should be None by default (not logged)
    assert logged_headers[0] is None


def test_request_context_set_by_auto_middleware(monkeypatch) -> None:
    from fapilog.core.errors import request_id_var

    class DummyLogger:
        async def info(self, message: str, **metadata) -> None:
            return None

        async def error(self, message: str, **metadata) -> None:
            return None

        async def drain(self) -> None:
            return None

    async def fake_get_async_logger(name: str | None = None, *, preset=None):
        return DummyLogger()

    monkeypatch.setattr("fapilog.get_async_logger", fake_get_async_logger)

    app = FastAPI(lifespan=setup_logging(preset="fastapi"))

    @app.get("/ctx")
    async def ctx(logger=Depends(get_request_logger)) -> dict[str, str]:
        assert request_id_var.get(None) == "rid-123"
        await logger.info("ctx")
        return {"ok": "yes"}

    with TestClient(app) as client:
        response = client.get("/ctx", headers={"X-Request-ID": "rid-123"})
        assert response.status_code == 200
