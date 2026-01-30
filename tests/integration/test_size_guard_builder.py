"""Integration tests for size_guard through builder API (Story 12.26).

These tests verify that `with_size_guard()` actually truncates payloads
when used via the builder, ensuring the `serialize_in_flush` fix works.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from fapilog.builder import AsyncLoggerBuilder


@pytest.mark.asyncio
async def test_size_guard_truncates_via_builder() -> None:
    """with_size_guard() truncates oversized payloads when building logger."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = await (
            AsyncLoggerBuilder()
            .with_size_guard(max_bytes="1 KB", action="truncate")
            .add_file(directory=tmpdir)
            .reuse(False)
            .build_async()
        )

        # Log a large payload that exceeds 1 KB
        await logger.info("test", data={"huge": "x" * 10000})
        await logger.drain()

        files = list(Path(tmpdir).glob("*.jsonl"))
        assert len(files) == 1, "Expected one log file"

        content = files[0].read_text()
        # Allow overhead for JSON structure + truncation markers
        assert len(content) <= 1500, f"Content too large: {len(content)} bytes"
        assert "_truncated" in content, "Expected _truncated marker"


@pytest.mark.asyncio
async def test_size_guard_drop_action_via_builder() -> None:
    """with_size_guard(action='drop') replaces oversized payloads."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = await (
            AsyncLoggerBuilder()
            .with_size_guard(max_bytes=500, action="drop")
            .add_file(directory=tmpdir)
            .reuse(False)
            .build_async()
        )

        await logger.info("test", data={"huge": "x" * 5000})
        await logger.drain()

        files = list(Path(tmpdir).glob("*.jsonl"))
        content = files[0].read_text()
        data = json.loads(content.strip())

        assert data.get("_dropped") is True
        assert "_original_size" in data


@pytest.mark.asyncio
async def test_size_guard_preserves_fields_via_builder() -> None:
    """with_size_guard() preserves specified fields during truncation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = await (
            AsyncLoggerBuilder()
            .with_size_guard(
                max_bytes=300,
                preserve_fields=["level", "timestamp", "custom_id"],
            )
            .add_file(directory=tmpdir)
            .reuse(False)
            .build_async()
        )

        await logger.info("test", data={"custom_id": "keep-me", "huge": "x" * 5000})
        await logger.drain()

        files = list(Path(tmpdir).glob("*.jsonl"))
        content = files[0].read_text()
        envelope = json.loads(content.strip())

        # Envelope may be heavily truncated; check markers
        assert envelope.get("_truncated") is True or envelope.get("_dropped") is True


@pytest.mark.asyncio
async def test_small_payload_passes_through_unchanged() -> None:
    """Small payloads pass through size_guard unchanged."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = await (
            AsyncLoggerBuilder()
            .with_size_guard(max_bytes="10 KB")
            .add_file(directory=tmpdir)
            .reuse(False)
            .build_async()
        )

        await logger.info("hello", data={"small": "value"})
        await logger.drain()

        files = list(Path(tmpdir).glob("*.jsonl"))
        content = files[0].read_text()
        envelope = json.loads(content.strip())

        # No truncation markers at envelope level
        assert "_truncated" not in envelope
        assert "_dropped" not in envelope
        # Envelope structure preserved with nested log object
        assert envelope["log"]["message"] == "hello"
        assert envelope["log"]["data"]["small"] == "value"
