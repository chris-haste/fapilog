from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from fapilog import Settings, get_logger


@pytest.mark.asyncio
async def test_audit_sink_pipeline_writes_logs(tmp_path: Path) -> None:
    settings = Settings()
    settings.core.sinks = ["audit"]
    settings.sink_config.audit.storage_path = str(tmp_path)
    settings.sink_config.audit.compliance_level = "gdpr"

    logger = get_logger(name="audit-test", settings=settings)

    logger.info("read resource", user_id="u-1", contains_pii=True)
    logger.error("failed operation", user_id="u-1")

    res = await logger.stop_and_drain()
    assert res.submitted >= 2
    await asyncio.sleep(0.1)

    files = list(Path(tmp_path).glob("audit_*.jsonl"))
    assert files, "audit sink should persist audit log file"
    with open(files[0], encoding="utf-8") as f:
        events = [json.loads(line) for line in f if line.strip()]
    assert any(e.get("event_type") == "error_occurred" for e in events)
    assert any(e.get("event_type") == "data_access" for e in events)
