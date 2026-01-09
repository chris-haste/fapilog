import asyncio
import logging
import sys
import threading
import time

import pytest

from fapilog.core import stdlib_bridge as bridge


@pytest.fixture(autouse=True)
def cleanup_bridge_loop() -> None:
    yield
    bridge._bridge_loop_manager.shutdown()


def test_extract_extras_includes_custom_fields() -> None:
    record = logging.LogRecord(
        name="app",
        level=logging.INFO,
        pathname=__file__,
        lineno=42,
        msg="msg",
        args=(),
        exc_info=None,
    )
    record.custom_field = "custom"
    record._private = "skip"

    extras = bridge._extract_extras(record)

    assert extras["custom_field"] == "custom"
    assert "_private" not in extras
    assert extras["stdlib_logger"] == "app"
    assert extras["filename"] == record.filename
    assert extras["lineno"] == 42


def test_emit_skips_fapilog_prefix() -> None:
    called = False

    class CaptureLogger:
        def debug(self, message: str, **_extras: object) -> None:
            _ = message

        def info(self, message: str, **_extras: object) -> None:
            _ = message

        def warning(self, message: str, **_extras: object) -> None:
            _ = message

        def error(self, message: str, **_extras: object) -> None:
            nonlocal called
            _ = message
            called = True

    handler = bridge.StdlibBridgeHandler(CaptureLogger())
    record = logging.LogRecord(
        name="fapilog.internal",
        level=logging.ERROR,
        pathname=__file__,
        lineno=10,
        msg="msg",
        args=(),
        exc_info=None,
    )

    handler.emit(record)

    assert called is False


def test_emit_critical_passes_exc_info_and_stack_info() -> None:
    captured: dict[str, object] = {}

    class CaptureLogger:
        def debug(self, message: str, **_extras: object) -> None:
            _ = message

        def info(self, message: str, **_extras: object) -> None:
            _ = message

        def warning(self, message: str, **_extras: object) -> None:
            _ = message

        def error(self, message: str, **extras: object) -> None:
            captured["message"] = message
            captured["extras"] = extras

    handler = bridge.StdlibBridgeHandler(CaptureLogger())
    try:
        raise ValueError("boom")
    except ValueError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="app",
        level=logging.CRITICAL,
        pathname=__file__,
        lineno=10,
        msg="critical",
        args=(),
        exc_info=exc_info,
    )
    record.stack_info = "stack"
    record.custom_field = "custom"

    handler.emit(record)

    extras = captured["extras"]
    assert captured["message"] == "critical"
    assert isinstance(extras, dict)
    assert extras["critical"] is True
    assert extras["stack_info"] == "stack"
    assert extras["custom_field"] == "custom"
    assert extras["exc_info"] == exc_info


def test_emit_warning_uses_warning_method() -> None:
    called = False

    class CaptureLogger:
        def debug(self, message: str, **_extras: object) -> None:
            _ = message

        def info(self, message: str, **_extras: object) -> None:
            _ = message

        def warning(self, message: str, **_extras: object) -> None:
            nonlocal called
            _ = message
            called = True

        def error(self, message: str, **_extras: object) -> None:
            _ = message

    handler = bridge.StdlibBridgeHandler(CaptureLogger())
    record = logging.LogRecord(
        name="app",
        level=logging.WARNING,
        pathname=__file__,
        lineno=10,
        msg="warn",
        args=(),
        exc_info=None,
    )

    handler.emit(record)

    assert called is True


def test_emit_info_uses_info_method() -> None:
    called = False

    class CaptureLogger:
        def debug(self, message: str, **_extras: object) -> None:
            _ = message

        def info(self, message: str, **_extras: object) -> None:
            nonlocal called
            _ = message
            called = True

        def warning(self, message: str, **_extras: object) -> None:
            _ = message

        def error(self, message: str, **_extras: object) -> None:
            _ = message

    handler = bridge.StdlibBridgeHandler(CaptureLogger())
    record = logging.LogRecord(
        name="app",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="info",
        args=(),
        exc_info=None,
    )

    handler.emit(record)

    assert called is True


def test_emit_error_does_not_mark_critical() -> None:
    captured: dict[str, object] = {}

    class CaptureLogger:
        def debug(self, message: str, **_extras: object) -> None:
            _ = message

        def info(self, message: str, **_extras: object) -> None:
            _ = message

        def warning(self, message: str, **_extras: object) -> None:
            _ = message

        def error(self, message: str, **extras: object) -> None:
            captured["extras"] = extras

    handler = bridge.StdlibBridgeHandler(CaptureLogger())
    record = logging.LogRecord(
        name="app",
        level=logging.ERROR,
        pathname=__file__,
        lineno=10,
        msg="err",
        args=(),
        exc_info=None,
    )

    handler.emit(record)

    extras = captured["extras"]
    assert isinstance(extras, dict)
    assert "critical" not in extras


def test_emit_debug_uses_debug_method() -> None:
    called = False

    class CaptureLogger:
        def debug(self, message: str, **_extras: object) -> None:
            nonlocal called
            _ = message
            called = True

        def info(self, message: str, **_extras: object) -> None:
            _ = message

        def warning(self, message: str, **_extras: object) -> None:
            _ = message

        def error(self, message: str, **_extras: object) -> None:
            _ = message

    handler = bridge.StdlibBridgeHandler(CaptureLogger())
    record = logging.LogRecord(
        name="app",
        level=logging.DEBUG,
        pathname=__file__,
        lineno=10,
        msg="debug",
        args=(),
        exc_info=None,
    )

    handler.emit(record)

    assert called is True


def test_emit_swallows_logger_exceptions() -> None:
    class ExplodingLogger:
        def debug(self, message: str, **_extras: object) -> None:
            _ = message
            raise RuntimeError("boom")

        def info(self, message: str, **_extras: object) -> None:
            _ = message
            raise RuntimeError("boom")

        def warning(self, message: str, **_extras: object) -> None:
            _ = message
            raise RuntimeError("boom")

        def error(self, message: str, **_extras: object) -> None:
            _ = message
            raise RuntimeError("boom")

    handler = bridge.StdlibBridgeHandler(ExplodingLogger())
    record = logging.LogRecord(
        name="app",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="msg",
        args=(),
        exc_info=None,
    )

    handler.emit(record)


def test_emit_force_sync_skips_coroutine() -> None:
    async def _noop() -> None:
        return None

    class AsyncLogger:
        def _closed_coro(self):
            coro = _noop()
            coro.close()
            return coro

        def debug(self, message: str, **_extras: object):
            _ = message
            return self._closed_coro()

        def info(self, message: str, **_extras: object):
            _ = message
            return self._closed_coro()

        def warning(self, message: str, **_extras: object):
            _ = message
            return self._closed_coro()

        def error(self, message: str, **_extras: object):
            _ = message
            return self._closed_coro()

    handler = bridge.StdlibBridgeHandler(AsyncLogger(), force_sync=True)
    record = logging.LogRecord(
        name="app",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="msg",
        args=(),
        exc_info=None,
    )

    handler.emit(record)

    assert bridge._bridge_loop_manager.is_running is False


def test_submit_returns_false_when_start_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = bridge._BridgeLoopManager()

    def _start(**_kwargs: object) -> None:
        return None

    monkeypatch.setattr(manager, "start", _start)

    async def _noop() -> None:
        return None

    coro = _noop()
    try:
        assert manager.submit(coro) is False
    finally:
        coro.close()


def test_submit_returns_false_on_run_coroutine_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = bridge._BridgeLoopManager()
    loop = asyncio.new_event_loop()
    monkeypatch.setattr(manager, "start", lambda **_kwargs: loop)
    monkeypatch.setattr(
        asyncio,
        "run_coroutine_threadsafe",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    async def _noop() -> None:
        return None

    coro = _noop()
    try:
        assert manager.submit(coro) is False
    finally:
        coro.close()
        loop.close()


def test_enable_stdlib_bridge_on_root_logger() -> None:
    root_logger = logging.getLogger()
    root_logger.handlers = [logging.NullHandler()]
    try:
        bridge.enable_stdlib_bridge(
            logger=object(),
            level=logging.WARNING,
            remove_existing_handlers=True,
            capture_warnings=True,
        )
        assert root_logger.level == logging.WARNING
        assert len(root_logger.handlers) == 1
        assert isinstance(root_logger.handlers[0], bridge.StdlibBridgeHandler)
    finally:
        root_logger.handlers = []
        logging.captureWarnings(False)


def test_enable_stdlib_bridge_with_target_loggers() -> None:
    logger = logging.getLogger("fapilog.tests.bridge")
    logger.handlers = [logging.NullHandler()]
    try:
        bridge.enable_stdlib_bridge(
            logger=object(),
            target_loggers=[logger],
            remove_existing_handlers=True,
        )
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], bridge.StdlibBridgeHandler)
    finally:
        logger.handlers = []


def test_enable_stdlib_bridge_keeps_existing_handlers() -> None:
    logger = logging.getLogger("fapilog.tests.bridge.keep")
    existing = logging.NullHandler()
    logger.handlers = [existing]
    try:
        bridge.enable_stdlib_bridge(
            logger=object(),
            target_loggers=[logger],
            remove_existing_handlers=False,
        )
        assert existing in logger.handlers
        assert any(
            isinstance(handler, bridge.StdlibBridgeHandler)
            for handler in logger.handlers
        )
    finally:
        logger.handlers = []


def test_bridge_loop_manager_shutdown_drains_pending_tasks() -> None:
    manager = bridge._BridgeLoopManager(thread_name="fapilog-test-bridge")
    loop = manager.start(timeout=1.0)
    assert isinstance(loop, asyncio.AbstractEventLoop)

    async def pending_task() -> None:
        await asyncio.sleep(0.1)

    manager.submit(pending_task(), timeout=1.0)
    manager.shutdown(timeout=1.0)

    assert manager.is_running is False


@pytest.mark.asyncio
async def test_emit_uses_running_loop_without_background_thread() -> None:
    called = asyncio.Event()

    class AsyncLogger:
        async def info(self, message: str, **_extras: object) -> None:
            _ = message
            called.set()

        async def debug(self, message: str, **_extras: object) -> None:
            await self.info(message, **_extras)

        async def warning(self, message: str, **_extras: object) -> None:
            await self.info(message, **_extras)

        async def error(self, message: str, **_extras: object) -> None:
            _ = message
            called.set()

    handler = bridge.StdlibBridgeHandler(AsyncLogger())
    record = logging.LogRecord(
        name="app",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="msg",
        args=(),
        exc_info=None,
    )

    handler.emit(record)

    await asyncio.wait_for(called.wait(), timeout=1.0)
    assert bridge._bridge_loop_manager.is_running is False


def test_emit_without_loop_uses_background_thread_nonblocking() -> None:
    called = threading.Event()

    class AsyncLogger:
        async def info(self, message: str, **_extras: object) -> None:
            _ = message
            called.set()

        async def debug(self, message: str, **_extras: object) -> None:
            await self.info(message, **_extras)

        async def warning(self, message: str, **_extras: object) -> None:
            await self.info(message, **_extras)

        async def error(self, message: str, **_extras: object) -> None:
            _ = message
            called.set()

    handler = bridge.StdlibBridgeHandler(AsyncLogger())
    record = logging.LogRecord(
        name="app",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="msg",
        args=(),
        exc_info=None,
    )

    handler.emit(record)

    assert called.wait(timeout=1.5)
    assert bridge._bridge_loop_manager.is_running is True


def test_force_sync_skips_background_loop() -> None:
    called = threading.Event()

    class SyncLogger:
        def info(self, message: str, **_extras: object) -> None:
            _ = message
            called.set()

        def debug(self, message: str, **_extras: object) -> None:
            self.info(message, **_extras)

        def warning(self, message: str, **_extras: object) -> None:
            self.info(message, **_extras)

        def error(self, message: str, **_extras: object) -> None:
            _ = message
            called.set()

    handler = bridge.StdlibBridgeHandler(SyncLogger(), force_sync=True)
    record = logging.LogRecord(
        name="app",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="msg",
        args=(),
        exc_info=None,
    )

    handler.emit(record)

    assert called.wait(timeout=0.5)
    assert bridge._bridge_loop_manager.is_running is False


def test_shutdown_stops_background_loop() -> None:
    called = threading.Event()

    class AsyncLogger:
        async def info(self, message: str, **_extras: object) -> None:
            _ = message
            called.set()

        async def debug(self, message: str, **_extras: object) -> None:
            await self.info(message, **_extras)

        async def warning(self, message: str, **_extras: object) -> None:
            await self.info(message, **_extras)

        async def error(self, message: str, **_extras: object) -> None:
            _ = message
            called.set()

    handler = bridge.StdlibBridgeHandler(AsyncLogger())
    record = logging.LogRecord(
        name="app",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="msg",
        args=(),
        exc_info=None,
    )

    handler.emit(record)
    assert called.wait(timeout=1.5)
    assert bridge._bridge_loop_manager.is_running is True

    bridge._bridge_loop_manager.shutdown(timeout=1.0)
    assert bridge._bridge_loop_manager.is_running is False

    bridge._bridge_loop_manager.shutdown(timeout=1.0)
    assert bridge._bridge_loop_manager.is_running is False


@pytest.mark.slow
def test_background_bridge_stress_low_overhead() -> None:
    target = 300
    lock = threading.Lock()
    done = threading.Event()
    processed = 0

    class AsyncLogger:
        async def info(self, message: str, **_extras: object) -> None:
            nonlocal processed
            _ = message
            with lock:
                processed += 1
                if processed >= target:
                    done.set()

        async def debug(self, message: str, **_extras: object) -> None:
            await self.info(message, **_extras)

        async def warning(self, message: str, **_extras: object) -> None:
            await self.info(message, **_extras)

        async def error(self, message: str, **_extras: object) -> None:
            await self.info(message, **_extras)

    handler = bridge.StdlibBridgeHandler(AsyncLogger())
    record = logging.LogRecord(
        name="app",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="msg",
        args=(),
        exc_info=None,
    )

    start = time.perf_counter()
    for _ in range(target):
        handler.emit(record)

    assert done.wait(timeout=5.0)
    assert processed == target
    assert bridge._bridge_loop_manager.is_running is True
    assert (time.perf_counter() - start) < 5.0
