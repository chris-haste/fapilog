from __future__ import annotations

import io
import sys

import pytest

from fapilog import get_logger
from fapilog.core.serialization import serialize_mapping_to_json_bytes


@pytest.mark.asyncio
async def test_get_logger_sink_write_serialized_wrapper_writes_stdout() -> None:
    # get_logger() chooses stdout sink by default when no file env is set.
    logger = get_logger(name="t-fastpath")

    # Capture stdout bytes
    buf = io.BytesIO()
    orig_stdout = sys.stdout
    sys.stdout = io.TextIOWrapper(buf, encoding="utf-8")  # type: ignore[assignment]
    try:
        view = serialize_mapping_to_json_bytes({"a": 1})
        # Call the duck-typed wrapper wired by get_logger
        await logger._sink_write_serialized(view)  # type: ignore[attr-defined]
        sys.stdout.flush()
        text = buf.getvalue().decode("utf-8").strip()
        assert text == '{"a":1}'
    finally:
        sys.stdout = orig_stdout  # type: ignore[assignment]

    # Clean up logger to avoid background tasks lingering
    await logger.stop_and_drain()
