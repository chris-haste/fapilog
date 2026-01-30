"""Integration tests for first_occurrence filter via builder (Story 12.27).

These tests verify that the first_occurrence filter actually deduplicates
messages when configured through the builder API.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from fapilog import _build_pipeline
from fapilog.builder import AsyncLoggerBuilder
from fapilog.core.settings import Settings

pytestmark = pytest.mark.integration


class TestFirstOccurrenceDeduplication:
    """Tests for AC1: first_occurrence deduplicates via builder."""

    @pytest.mark.asyncio
    async def test_first_occurrence_deduplicates_via_builder(self) -> None:
        """Duplicate messages are filtered when using with_first_occurrence()."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = await (
                AsyncLoggerBuilder()
                .with_first_occurrence(window_seconds=60.0, max_keys=1000)
                .add_file(directory=tmpdir)
                .reuse(False)
                .build_async()
            )

            for _ in range(10):
                await logger.info("Duplicate message")
            await logger.drain()

            files = list(Path(tmpdir).glob("*.jsonl"))
            assert len(files) == 1
            content = files[0].read_text()
            lines = [line for line in content.strip().split("\n") if line]
            duplicate_count = sum(1 for line in lines if "Duplicate message" in line)
            assert duplicate_count == 1

    @pytest.mark.asyncio
    async def test_first_occurrence_unique_messages_pass(self) -> None:
        """Unique messages all pass through the filter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = await (
                AsyncLoggerBuilder()
                .with_first_occurrence(window_seconds=60.0, max_keys=1000)
                .add_file(directory=tmpdir)
                .reuse(False)
                .build_async()
            )

            for i in range(5):
                await logger.info(f"Unique message {i}")
            await logger.drain()

            files = list(Path(tmpdir).glob("*.jsonl"))
            content = files[0].read_text()
            lines = [line for line in content.strip().split("\n") if line]
            assert len(lines) == 5


class TestFirstOccurrenceFilterLoads:
    """Tests for AC4: filter actually loads in the pipeline."""

    def test_first_occurrence_filter_loads_with_max_keys(self) -> None:
        """Filter loads when config uses max_keys."""
        settings = Settings(
            core={"filters": ["first_occurrence"]},
            filter_config={
                "first_occurrence": {"window_seconds": 60.0, "max_keys": 1000}
            },
        )

        _, _, _, _, filters, _ = _build_pipeline(settings)

        assert len(filters) == 1
        assert filters[0].__class__.__name__ == "FirstOccurrenceFilter"

    def test_first_occurrence_filter_loads_via_builder_config(self) -> None:
        """Filter loads when configured via builder."""
        builder = AsyncLoggerBuilder().with_first_occurrence(
            window_seconds=60.0, max_keys=1000
        )

        settings = Settings(
            core=builder._config.get("core"),
            filter_config=builder._config.get("filter_config"),
        )

        _, _, _, _, filters, _ = _build_pipeline(settings)

        assert len(filters) == 1
        assert filters[0].__class__.__name__ == "FirstOccurrenceFilter"
