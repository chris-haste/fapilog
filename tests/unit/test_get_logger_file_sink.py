from __future__ import annotations

import asyncio
from pathlib import Path

from fapilog import get_logger


def test_get_logger_uses_file_sink_when_env_set(tmp_path: Path, monkeypatch) -> None:
    # Point file sink to a temp directory to exercise rotating-file branch
    monkeypatch.setenv("FAPILOG_FILE__DIRECTORY", str(tmp_path))

    logger = get_logger(name="file-branch")
    logger.info("hello-file")

    # Drain synchronously
    asyncio.run(logger.stop_and_drain())

    # Expect a .jsonl file created in the directory
    files = [p for p in tmp_path.iterdir() if p.is_file()]
    assert any(p.suffix == ".jsonl" for p in files)
