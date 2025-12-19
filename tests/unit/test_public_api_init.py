from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from fapilog import get_logger, runtime
from fapilog.core.settings import Settings


def test_get_logger_rotating_file_sink_env_writes_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAPILOG_FILE__DIRECTORY", str(tmp_path))
    logger = get_logger(name="rot-file-test")
    logger.info("hello")
    # Drain synchronously
    asyncio.run(logger.stop_and_drain())
    # Expect at least one file created in the directory
    files = list(tmp_path.iterdir())
    assert any(p.is_file() for p in files)


@pytest.mark.filterwarnings(
    "ignore:coroutine 'SyncLoggerFacade.stop_and_drain' was never awaited:RuntimeWarning"
)
@pytest.mark.asyncio
async def test_runtime_inside_running_loop_drains_via_create_task() -> None:
    # Using runtime in-loop should exercise the create_task drain path
    async with _runtime_cm() as logger:
        logger.info("x")
        await asyncio.sleep(0)
    # Allow the drain task done-callback to run before test teardown
    await asyncio.sleep(0.02)


class _runtime_cm:
    # Thin async wrapper to use sync contextmanager in async test
    def __init__(self) -> None:
        self._cm = runtime()

    async def __aenter__(self):
        return self._cm.__enter__()

    async def __aexit__(self, exc_type, exc, tb):
        self._cm.__exit__(exc_type, exc, tb)
        await asyncio.sleep(0)


def test_get_logger_policy_warn_and_bind(monkeypatch: pytest.MonkeyPatch) -> None:
    s = Settings()
    s.core.sensitive_fields_policy = ["user.password"]
    s.core.default_bound_context = {"tenant": "t1"}
    logger = get_logger(name="policy-test", settings=s)
    logger.info("x")
    asyncio.run(logger.stop_and_drain())


def test_public_version_exposed():
    from fapilog import __version__

    assert isinstance(__version__, str) and __version__


def test_public_version_constant():
    from fapilog import VERSION

    assert isinstance(VERSION, str) and VERSION
