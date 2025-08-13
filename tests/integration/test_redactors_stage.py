from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest

from fapilog import get_logger
from fapilog.metrics.metrics import MetricsCollector
from fapilog.plugins.enrichers import BaseEnricher
from fapilog.plugins.redactors import BaseRedactor


class _StubEnricher:
    name = "stub_enricher"

    async def enrich(self, event: dict) -> dict:
        base = dict(event)
        base["value"] = base.get("value", 0) + 1
        base["enriched"] = True
        return base


class _StubRedactorAdd10:
    name = "stub_redactor_add10"

    async def redact(self, event: dict) -> dict:
        base = dict(event)
        base["value"] = base.get("value", 0) + 10
        base["redacted_by"] = base.get("redacted_by", []) + ["r10"]
        return base


class _StubRedactorAdd100:
    name = "stub_redactor_add100"

    async def redact(self, event: dict) -> dict:
        base = dict(event)
        base["value"] = base.get("value", 0) + 100
        base["redacted_by"] = base.get("redacted_by", []) + ["r100"]
        return base


class _StubRedactorBoom:
    name = "stub_redactor_boom"

    async def redact(self, event: dict) -> dict:  # pragma: no cover
        raise RuntimeError("boom")


async def _collecting_sink(
    collected: list[dict[str, Any]], entry: dict[str, Any]
) -> None:
    collected.append(dict(entry))


@pytest.mark.asyncio
async def test_redactors_ordering_and_integration() -> None:
    collected: list[dict[str, Any]] = []

    logger = get_logger(name="redactors-test")

    # Replace sink to capture output
    async def _sink(entry: dict[str, Any]) -> None:
        await _collecting_sink(collected, entry)

    logger._sink_write = _sink  # type: ignore[attr-defined]

    # Inject stub enricher and redactors
    # Note: type ignores are expected; we are injecting test doubles
    logger._enrichers = cast(
        list[BaseEnricher],
        [_StubEnricher()],
    )  # type: ignore[attr-defined]
    logger._redactors = cast(
        list[BaseRedactor],
        [
            _StubRedactorAdd10(),
            _StubRedactorAdd100(),
        ],
    )  # type: ignore[attr-defined]

    logger.info("hello")
    await asyncio.sleep(0)
    await logger.stop_and_drain()

    assert collected, "Expected at least one emitted entry"
    event = collected[0]
    # Enricher ran first, then redactors, then sink
    assert event.get("enriched") is True
    # Redactors applied sequentially: 0->+1 (enricher)->+10->+100 == 111
    assert event.get("value") == 111
    assert event.get("redacted_by") == ["r10", "r100"]


@pytest.mark.asyncio
async def test_redactor_error_handling_no_drop() -> None:
    collected: list[dict[str, Any]] = []

    logger = get_logger(name="redactors-error-test")
    # Enable metrics to exercise plugin_timer error path
    logger._metrics = MetricsCollector(enabled=True)  # type: ignore[attr-defined]

    async def _sink2(entry: dict[str, Any]) -> None:
        await _collecting_sink(collected, entry)

    logger._sink_write = _sink2  # type: ignore[attr-defined]
    logger._enrichers = cast(
        list[BaseEnricher],
        [_StubEnricher()],
    )  # type: ignore[attr-defined]
    logger._redactors = cast(
        list[BaseRedactor],
        [
            _StubRedactorBoom(),
            _StubRedactorAdd10(),
        ],
    )  # type: ignore[attr-defined]

    logger.info("x")
    await asyncio.sleep(0)
    res = await logger.stop_and_drain()

    assert res.submitted >= 1
    assert res.processed >= 1
    assert collected, "Event should not be dropped on redactor error"
    # boom redactor contained; at least enriched
    assert collected[0].get("value") in (1, 11)
