import asyncio
import logging
import threading
import time

import pytest

from fapilog.core import stdlib_bridge as bridge


@pytest.fixture(autouse=True)
def cleanup_bridge_loop() -> None:
    yield
    bridge._bridge_loop_manager.shutdown()


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
