from __future__ import annotations

import asyncio
import io
import json
import sys
from pathlib import Path

import pytest

from fapilog import get_logger


@pytest.mark.asyncio
async def test_stdout_fastpath_on_off_equivalence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Capture stdout
    buf_on = io.BytesIO()
    buf_off = io.BytesIO()

    def _swap_stdout(target: io.BytesIO) -> object:
        orig = sys.stdout
        sys.stdout = io.TextIOWrapper(target, encoding="utf-8")  # type: ignore[assignment]
        return orig

    # Common env
    monkeypatch.delenv("FAPILOG_FILE__DIRECTORY", raising=False)
    monkeypatch.setenv("FAPILOG_ENABLE_METRICS", "0")
    monkeypatch.setenv("FAPILOG_CORE__STRICT_ENVELOPE_MODE", "0")

    # Fastpath ON
    monkeypatch.setenv("FAPILOG_CORE__SERIALIZE_IN_FLUSH", "1")
    orig = _swap_stdout(buf_on)
    try:
        logger_on = get_logger("t")
        logger_on.info("m", extra={"a": 1})
        await asyncio.sleep(0.05)
        await logger_on.stop_and_drain()
        # Capture output before restoring stdout to avoid closing buffer
        sys.stdout.flush()
        text_on = buf_on.getvalue().decode("utf-8")
    finally:
        sys.stdout = orig  # type: ignore[assignment]

    # Fastpath OFF
    monkeypatch.setenv("FAPILOG_CORE__SERIALIZE_IN_FLUSH", "0")
    orig = _swap_stdout(buf_off)
    try:
        logger_off = get_logger("t")
        logger_off.info("m", extra={"a": 1})
        await asyncio.sleep(0.05)
        await logger_off.stop_and_drain()
        sys.stdout.flush()
        text_off = buf_off.getvalue().decode("utf-8")
    finally:
        sys.stdout = orig  # type: ignore[assignment]

    # Compare JSON objects line by line
    lines_on = [ln for ln in text_on.splitlines() if ln]
    lines_off = [ln for ln in text_off.splitlines() if ln]
    assert len(lines_on) == len(lines_off) == 1
    obj_on = json.loads(lines_on[0])
    obj_off = json.loads(lines_off[0])

    def _normalize(obj: dict) -> dict:
        # Remove dynamic fields; handle envelope form if present
        if "schema_version" in obj and "log" in obj:
            log = dict(obj["log"])  # shallow copy
            log.pop("timestamp", None)
            log.pop("correlation_id", None)
            return {"schema_version": obj["schema_version"], "log": log}
        else:
            copy = dict(obj)
            copy.pop("timestamp", None)
            copy.pop("correlation_id", None)
            return copy

    assert _normalize(obj_on) == _normalize(obj_off)


@pytest.mark.asyncio
async def test_rotating_file_fastpath_on_off_equivalence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Configure rotating file via env
    monkeypatch.setenv("FAPILOG_FILE__DIRECTORY", str(tmp_path))
    monkeypatch.setenv("FAPILOG_FILE__MODE", "json")
    monkeypatch.setenv("FAPILOG_ENABLE_METRICS", "0")
    monkeypatch.setenv("FAPILOG_CORE__STRICT_ENVELOPE_MODE", "0")

    async def _produce(fastpath: bool) -> list[str]:
        monkeypatch.setenv("FAPILOG_CORE__SERIALIZE_IN_FLUSH", "1" if fastpath else "0")
        logger = get_logger("t")
        for i in range(5):
            logger.info("m", extra={"i": i})
        await asyncio.sleep(0.1)
        await logger.stop_and_drain()
        # Read all files and collect lines
        out: list[str] = []
        for p in sorted(tmp_path.iterdir()):
            if p.is_file() and (p.suffix == ".jsonl" or p.name.endswith(".jsonl")):
                out.extend([ln for ln in p.read_text().splitlines() if ln])
        return out

    lines_on = await _produce(True)
    # Clean directory for off run
    for p in list(tmp_path.iterdir()):
        try:
            if p.is_file():
                p.unlink()
        except Exception:
            pass
    lines_off = await _produce(False)

    assert len(lines_on) == len(lines_off) == 5
    # Compare JSON objects order-preserving
    objs_on = [json.loads(ln) for ln in lines_on]
    objs_off = [json.loads(ln) for ln in lines_off]

    def _normalize(obj: dict) -> dict:
        if "schema_version" in obj and "log" in obj:
            log = dict(obj["log"])
            log.pop("timestamp", None)
            log.pop("correlation_id", None)
            return {"schema_version": obj["schema_version"], "log": log}
        else:
            copy = dict(obj)
            copy.pop("timestamp", None)
            copy.pop("correlation_id", None)
            return copy

    assert [_normalize(o) for o in objs_on] == [_normalize(o) for o in objs_off]
