from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Iterable

_STD_ATTRS: set[str] = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
}


def _extract_extras(record: logging.LogRecord) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for key, value in record.__dict__.items():
        if key not in _STD_ATTRS and not key.startswith("_"):
            data[key] = value
    # Preserve basic origin info
    data.setdefault("stdlib_logger", record.name)
    data.setdefault("module", record.module)
    data.setdefault("filename", record.filename)
    data.setdefault("lineno", record.lineno)
    data.setdefault("funcName", record.funcName)
    return data


class _BridgeLoopManager:
    """Manages a shared background event loop for stdlib bridge submissions."""

    def __init__(self, *, thread_name: str = "fapilog-stdlib-bridge") -> None:
        self._thread_name = thread_name
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return (
            self._loop is not None
            and self._thread is not None
            and self._thread.is_alive()
        )

    def start(
        self,
        *,
        thread_name: str | None = None,
        timeout: float = 2.0,
    ) -> asyncio.AbstractEventLoop | None:
        with self._lock:
            if self.is_running and self._loop is not None:
                return self._loop
            name = thread_name or self._thread_name
            ready = threading.Event()
            self._ready = ready

            def _run() -> None:
                loop = asyncio.new_event_loop()
                self._loop = loop
                asyncio.set_event_loop(loop)
                ready.set()
                try:
                    loop.run_forever()
                finally:
                    try:
                        pending = asyncio.all_tasks(loop)
                        for task in pending:
                            task.cancel()
                        if pending:
                            loop.run_until_complete(
                                asyncio.gather(*pending, return_exceptions=True)
                            )
                    except Exception:
                        pass
                    try:
                        loop.close()
                    except Exception:
                        pass
                    self._loop = None

            thread = threading.Thread(target=_run, name=name, daemon=True)
            self._thread = thread
            thread.start()

        # Wait for loop to be ready
        ready.wait(timeout=timeout)
        return self._loop

    def submit(
        self,
        coro: Any,
        *,
        thread_name: str | None = None,
        timeout: float = 2.0,
    ) -> bool:
        loop = self.start(thread_name=thread_name, timeout=timeout)
        if loop is None:
            return False
        try:
            asyncio.run_coroutine_threadsafe(coro, loop)
            return True
        except Exception:
            return False

    def shutdown(self, *, timeout: float = 2.0) -> None:  # noqa
        loop = self._loop
        thread = self._thread
        if loop is None or thread is None:
            self._loop = None
            self._thread = None
            self._ready.clear()
            return

        async def _drain() -> None:
            tasks = [
                t
                for t in asyncio.all_tasks(loop)
                if t is not asyncio.current_task(loop)
            ]
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            loop.stop()

        try:
            fut = asyncio.run_coroutine_threadsafe(_drain(), loop)
            try:
                fut.result(timeout=timeout)
            except Exception:
                pass
        except Exception:
            try:
                loop.call_soon_threadsafe(loop.stop)
            except Exception:
                pass

        try:
            thread.join(timeout=timeout)
        except Exception:
            pass

        with self._lock:
            self._loop = None
            self._thread = None
            self._ready.clear()


_bridge_loop_manager = _BridgeLoopManager()


class StdlibBridgeHandler(logging.Handler):
    """Bridge stdlib LogRecord into fapilog's async pipeline.

    Non-blocking: emit() delegates immediately to the facade enqueue path.
    """

    def __init__(
        self,
        fapilog_logger: Any,
        *,
        level: int = logging.NOTSET,
        logger_namespace_prefix: str = "fapilog",
        force_sync: bool = False,
        loop_thread_name: str = "fapilog-stdlib-bridge",
        startup_timeout: float = 2.0,
    ) -> None:
        super().__init__(level)
        self._fl = fapilog_logger
        self._prefix = logger_namespace_prefix
        self._force_sync = bool(force_sync)
        self._loop_thread_name = loop_thread_name
        self._startup_timeout = float(startup_timeout)

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
        try:
            # Loop prevention: ignore records originating from fapilog
            if record.name.startswith(self._prefix):
                return
            message = record.getMessage()
            extras = _extract_extras(record)

            # Level mapping
            lvl = record.levelno
            method = self._fl.debug
            if lvl >= logging.CRITICAL:
                method = self._fl.critical
            elif lvl >= logging.ERROR:
                method = self._fl.error
            elif lvl >= logging.WARNING:
                method = self._fl.warning
            elif lvl >= logging.INFO:
                method = self._fl.info

            # Exception propagation
            exc_info = record.exc_info
            stack_info = record.stack_info
            if stack_info and "error.stack" not in extras:
                extras["stack_info"] = stack_info

            if exc_info:
                result = method(message, exc_info=exc_info, **extras)
            else:
                result = method(message, **extras)

            # If the target logger method is async, schedule it safely
            if asyncio.iscoroutine(result):
                if self._force_sync:
                    return
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(result)
                except RuntimeError:
                    # No running loop; schedule on shared background loop
                    _bridge_loop_manager.submit(
                        result,
                        thread_name=self._loop_thread_name,
                        timeout=self._startup_timeout,
                    )
        except Exception:
            # Bridge must never raise
            return


def enable_stdlib_bridge(
    logger: Any,
    *,
    level: int = logging.INFO,
    remove_existing_handlers: bool = False,
    capture_warnings: bool = False,
    logger_namespace_prefix: str = "fapilog",
    target_loggers: Iterable[logging.Logger] | None = None,
    force_sync: bool = False,
    loop_thread_name: str = "fapilog-stdlib-bridge",
    startup_timeout: float = 2.0,
) -> None:
    """Enable stdlib logging bridge.

    Installs a handler on the root (or provided target loggers) that forwards
    stdlib logs into the fapilog pipeline.
    """
    handler = StdlibBridgeHandler(
        logger,
        level=level,
        logger_namespace_prefix=logger_namespace_prefix,
        force_sync=force_sync,
        loop_thread_name=loop_thread_name,
        startup_timeout=startup_timeout,
    )
    targets: list[logging.Logger]
    if target_loggers is not None:
        targets = list(target_loggers)
    else:
        targets = [logging.getLogger()]  # root logger

    for lg in targets:
        lg.setLevel(level)
        if remove_existing_handlers:
            lg.handlers[:] = []
        lg.addHandler(handler)

    if capture_warnings:
        logging.captureWarnings(True)
