from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from fapilog import get_logger


def test_rotating_file_sink_env_compression_and_limits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAPILOG_FILE__DIRECTORY", str(tmp_path))
    monkeypatch.setenv("FAPILOG_FILE__MAX_BYTES", "128")
    monkeypatch.setenv("FAPILOG_FILE__MAX_FILES", "2")
    monkeypatch.setenv("FAPILOG_FILE__MAX_TOTAL_BYTES", "256")
    monkeypatch.setenv("FAPILOG_FILE__COMPRESS_ROTATED", "true")
    logger = get_logger(name="rot-factory")
    for i in range(200):
        logger.info("x", i=i)
    asyncio.run(logger.stop_and_drain())
    # Ensure directory has at least one file created (compressed or not)
    assert any(p.is_file() for p in tmp_path.iterdir())
