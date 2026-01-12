from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from fapilog import get_logger
from fapilog.sinks import rotating_file

pytestmark = pytest.mark.integration


def test_get_logger_with_rotating_file_factory(tmp_path: Path) -> None:
    log_path = tmp_path / "app.log"
    logger = get_logger(sinks=[rotating_file(log_path)])
    logger.info("factory integration test", event="startup")
    asyncio.run(logger.stop_and_drain())

    log_files = list(tmp_path.glob("app-*.jsonl"))
    assert log_files, "expected rotating file output to be created"
    assert "factory integration test" in log_files[0].read_text(encoding="utf-8")
