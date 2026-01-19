"""
Test logger context and correlation behavior.

Scope:
- Correlation ID generation from context variables
- Diagnostic emissions on errors

Does NOT cover:
- Context binding API (see test_logger_features.py)
- Error containment (see test_logger_errors.py)
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from fapilog import get_logger
from fapilog.core.diagnostics import set_writer_for_tests
from fapilog.core.errors import request_id_var
from fapilog.core.settings import Settings


class TestCorrelationId:
    """Tests for correlation ID generation from request context."""

    @pytest.mark.asyncio
    async def test_correlation_id_uses_context_request_id(self) -> None:
        captured: list[dict[str, Any]] = []
        logger = get_logger(name="corr")

        async def capture(entry: dict[str, Any]) -> None:
            captured.append(entry)

        logger._sink_write = capture  # type: ignore[attr-defined]

        token = request_id_var.set("REQ-123")
        try:
            logger.info("message")
            await logger.stop_and_drain()
        finally:
            request_id_var.reset(token)

        assert captured
        # v1.1 schema: correlation_id is in context
        assert captured[0].get("context", {}).get("correlation_id") == "REQ-123"


class TestDiagnostics:
    """Tests for internal diagnostic emissions."""

    @pytest.mark.asyncio
    async def test_flush_error_emits_diagnostics_and_drops_batch(
        self, monkeypatch: Any
    ) -> None:
        # Enable internal diagnostics via env so Settings picks it up
        monkeypatch.setenv("FAPILOG_CORE__INTERNAL_LOGGING_ENABLED", "true")

        # Build settings with small batch to force immediate flush
        s = Settings()
        s.core.batch_max_size = 2
        s.core.batch_timeout_seconds = 0.1

        logger = get_logger(name="diag", settings=s)

        # Capture diagnostics
        captured: list[dict[str, Any]] = []

        def capture_writer(payload: dict[str, Any]) -> None:
            captured.append(payload)

        set_writer_for_tests(capture_writer)

        # Sink that always raises to trigger error path in _flush_batch
        async def failing_sink(entry: dict[str, Any]) -> None:  # noqa: ARG001
            raise RuntimeError("sink failure")

        # Replace sink_write on the logger (test-only)
        logger._sink_write = failing_sink  # type: ignore[attr-defined]

        # Submit two events to form a batch and trigger flush
        logger.info("a")
        logger.info("b")

        # Allow the worker to attempt flush
        await asyncio.sleep(0.2)
        res = await logger.stop_and_drain()

        assert res.submitted == 2
        assert res.processed == 0
        assert res.dropped == 2

        # Verify at least one diagnostic was emitted for sink flush error
        assert any(
            p.get("component") == "sink" and p.get("level") in {"WARN", "WARNING"}
            for p in captured
        )
