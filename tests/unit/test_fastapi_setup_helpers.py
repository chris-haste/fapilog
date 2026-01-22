from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from fapilog.fastapi import get_request_logger, setup_logging
from fapilog.fastapi.context import RequestContextMiddleware
from fapilog.fastapi.logging import LoggingMiddleware
from fapilog.fastapi.setup import _configure_middleware, _drain_logger


def test_configure_middleware_adds_defaults_and_resets_stack() -> None:
    app = FastAPI()
    logger = object()

    _configure_middleware(
        app,
        logger=logger,
        skip_paths=["/health"],
        sample_rate=0.25,
        redact_headers=["authorization"],
    )

    names = [mw.cls.__name__ for mw in app.user_middleware]
    assert names[0] == "RequestContextMiddleware"
    assert names[1] == "LoggingMiddleware"
    logging_mw = next(
        mw for mw in app.user_middleware if mw.cls.__name__ == "LoggingMiddleware"
    )
    assert logging_mw.kwargs["logger"] is logger
    assert logging_mw.kwargs["skip_paths"] == ["/health"]
    assert logging_mw.kwargs["sample_rate"] == 0.25
    assert logging_mw.kwargs["redact_headers"] == ["authorization"]
    assert app.middleware_stack is None


def test_configure_middleware_propagates_log_errors_on_skip() -> None:
    """Test log_errors_on_skip is passed to LoggingMiddleware."""
    app = FastAPI()
    logger = object()

    _configure_middleware(
        app,
        logger=logger,
        log_errors_on_skip=False,
    )

    logging_mw = next(
        mw for mw in app.user_middleware if mw.cls.__name__ == "LoggingMiddleware"
    )
    assert logging_mw.kwargs["log_errors_on_skip"] is False


def test_configure_middleware_resets_stack_when_updated() -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.middleware_stack = object()
    logger = object()

    _configure_middleware(app, logger=logger)

    assert app.middleware_stack is None


def test_configure_middleware_inserts_logging_after_context() -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    logger = object()

    _configure_middleware(app, logger=logger)

    names = [mw.cls.__name__ for mw in app.user_middleware]
    assert names[0] == "RequestContextMiddleware"
    assert names[1] == "LoggingMiddleware"


def test_configure_middleware_updates_existing_logging_logger() -> None:
    app = FastAPI()
    app.add_middleware(LoggingMiddleware)
    logger = object()

    _configure_middleware(app, logger=logger)

    logging_mw = next(
        mw for mw in app.user_middleware if mw.cls.__name__ == "LoggingMiddleware"
    )
    assert logging_mw.kwargs["logger"] is logger
    assert any(
        mw.cls.__name__ == "RequestContextMiddleware" for mw in app.user_middleware
    )


def test_setup_logging_wraps_lifespan_and_drains(monkeypatch) -> None:
    events: list[str] = []

    class DummyLogger:
        async def drain(self) -> None:
            events.append("drain")

    async def fake_get_async_logger(name: str | None = None, *, preset=None):
        events.append(f"start:{name}:{preset}")
        return DummyLogger()

    monkeypatch.setattr("fapilog.get_async_logger", fake_get_async_logger)

    @asynccontextmanager
    async def user_lifespan(app: FastAPI):
        events.append("user_start")
        yield
        events.append("user_stop")

    app = FastAPI(lifespan=setup_logging(wrap_lifespan=user_lifespan, preset="fastapi"))

    with TestClient(app):
        pass

    assert events == ["start:fastapi:fastapi", "user_start", "user_stop", "drain"]


def test_setup_logging_auto_middleware_false_skips_wiring(monkeypatch) -> None:
    async def fake_get_async_logger(name: str | None = None, *, preset=None):
        class DummyLogger:
            async def drain(self) -> None:
                return None

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
async def test_get_request_logger_prefers_app_state() -> None:
    logger = object()
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(fapilog_logger=logger))
    )

    assert await get_request_logger(request) is logger


@pytest.mark.asyncio
async def test_get_request_logger_falls_back_to_async_logger(monkeypatch) -> None:
    logger = object()

    async def fake_get_async_logger(name: str | None = None, *, preset=None):
        return logger

    monkeypatch.setattr("fapilog.get_async_logger", fake_get_async_logger)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))

    assert await get_request_logger(request) is logger


@pytest.mark.asyncio
async def test_drain_logger_warns_on_timeout(monkeypatch) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    async def fake_drain() -> None:
        await asyncio.sleep(0.01)

    class DummyLogger:
        async def drain(self) -> None:
            await fake_drain()

    def fake_warn(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr("fapilog.fastapi.setup.warn", fake_warn)

    await _drain_logger(DummyLogger(), timeout=0.0)

    assert calls
    assert calls[0][0][1] == "logger drain timeout"


@pytest.mark.asyncio
async def test_drain_logger_warns_on_error(monkeypatch) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    class DummyLogger:
        async def drain(self) -> None:
            raise RuntimeError("boom")

    def fake_warn(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr("fapilog.fastapi.setup.warn", fake_warn)

    await _drain_logger(DummyLogger(), timeout=0.01)

    assert calls
    assert calls[0][0][1] == "logger drain failed"
