from __future__ import annotations

import logging
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
    ) -> None:
        super().__init__(level)
        self._fl = fapilog_logger
        self._prefix = logger_namespace_prefix

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
            if lvl >= logging.ERROR:
                method = self._fl.error
                if lvl >= logging.CRITICAL:
                    extras.setdefault("critical", True)
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
                method(message, exc_info=exc_info, **extras)
            else:
                method(message, **extras)
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
) -> None:
    """Enable stdlib logging bridge.

    Installs a handler on the root (or provided target loggers) that forwards
    stdlib logs into the fapilog pipeline.
    """
    handler = StdlibBridgeHandler(
        logger, level=level, logger_namespace_prefix=logger_namespace_prefix
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
