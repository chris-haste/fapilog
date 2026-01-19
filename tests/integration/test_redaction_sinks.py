"""
Redaction Integration Tests for All Sink Types

Story 7.3: Security-critical tests verifying that redaction is applied
before data reaches sink boundaries. These tests use real sinks (not mocks)
to verify masked data appears in actual output.

The tests verify:
- Masked data appears in stdout JSON output
- Masked data appears in file sink output
- Masked data appears in HTTP request bodies
- Masked data appears in PostgreSQL rows
- Redaction applies to all log levels
- Redaction happens before serialization
"""

from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from fapilog import get_logger
from fapilog.plugins.redactors import BaseRedactor
from fapilog.plugins.redactors.field_mask import FieldMaskRedactor

pytestmark = [pytest.mark.integration, pytest.mark.security]


def _swap_stdout_bytesio() -> tuple[io.BytesIO, Any]:
    """Swap stdout with a BytesIO buffer for capturing output."""
    buf = io.BytesIO()
    orig = sys.stdout
    sys.stdout = io.TextIOWrapper(buf, encoding="utf-8", newline="", write_through=True)
    return buf, orig


@pytest.mark.asyncio
@pytest.mark.security
async def test_redaction_reaches_stdout_sink() -> None:
    """Verify redacted data appears in stdout JSON output.

    This test captures actual stdout and verifies that:
    1. Sensitive fields are masked with ***
    2. Non-sensitive fields remain unchanged
    3. Raw secret values never appear in output
    """
    from fapilog.plugins.sinks.stdout_json import StdoutJsonSink

    buf, orig = _swap_stdout_bytesio()
    try:
        # Create real stdout sink
        sink = StdoutJsonSink()

        # Create real field mask redactor
        # Use data.* paths since fields are in data dict (v1.1 schema)
        redactor = FieldMaskRedactor(
            config={
                "fields_to_mask": [
                    "data.password",
                    "data.credit_card",
                    "data.user.ssn",
                ],
            }
        )

        logger = get_logger(name="redaction-stdout-test")
        logger._sink_write = sink.write  # type: ignore[attr-defined]
        logger._redactors = cast(list[BaseRedactor], [redactor])

        logger.info(
            "user_login",
            username="alice",
            password="secret123",
            credit_card="4111-1111-1111-1111",
            user={"name": "Alice", "ssn": "123-45-6789"},
        )

        await logger.stop_and_drain()
        sys.stdout.flush()

        # Get the captured output
        output = buf.getvalue().decode("utf-8")
    finally:
        sys.stdout = orig  # type: ignore[assignment]

    # Parse the JSON output
    assert output.strip(), "No output captured"
    envelope = json.loads(output.strip())

    # Serialized envelope wraps log in {"schema_version": "1.1", "log": {...}}
    log_entry = envelope.get("log", envelope)  # fallback for non-envelope output

    # Verify sensitive fields are masked (in data - v1.1 schema)
    data = log_entry.get("data", {})
    assert data.get("password") == "***", "password should be masked"
    assert data.get("credit_card") == "***", "credit_card should be masked"
    assert data.get("user", {}).get("ssn") == "***", "ssn should be masked"

    # Verify non-sensitive fields are NOT masked
    assert data.get("username") == "alice", "username should not be masked"
    assert data.get("user", {}).get("name") == "Alice", "name should not be masked"

    # Verify the actual secret values do NOT appear anywhere in raw output
    assert "secret123" not in output, "raw password leaked to output"
    assert "4111-1111-1111-1111" not in output, "raw credit_card leaked to output"
    assert "123-45-6789" not in output, "raw ssn leaked to output"


@pytest.mark.asyncio
@pytest.mark.security
async def test_redaction_reaches_file_sink(tmp_path: Path) -> None:
    """Verify redacted data appears in file sink output.

    This test writes to a real file and verifies that:
    1. Sensitive values never appear in the file
    2. Masked values appear in the file
    3. Non-sensitive data is preserved
    """
    from fapilog.plugins.sinks.rotating_file import (
        RotatingFileSink,
        RotatingFileSinkConfig,
    )

    # Create real file sink
    sink = RotatingFileSink(
        RotatingFileSinkConfig(
            directory=tmp_path,
            filename_prefix="test",
            max_bytes=10_000_000,
        )
    )
    await sink.start()

    try:
        # Create redactor (v1.1 schema uses data.* paths)
        redactor = FieldMaskRedactor(
            config={
                "fields_to_mask": ["data.api_key", "data.token"],
            }
        )

        logger = get_logger(name="redaction-file-test")
        logger._sink_write = sink.write  # type: ignore[attr-defined]
        logger._redactors = cast(list[BaseRedactor], [redactor])

        logger.info(
            "api_call", api_key="sk-12345", token="bearer-xyz", endpoint="/users"
        )

        await logger.stop_and_drain()
    finally:
        await sink.stop()

    # Find the log file (JSON mode creates .jsonl files)
    log_files = list(tmp_path.glob("test*.jsonl"))
    assert log_files, "No log file created"
    content = log_files[0].read_text()

    # Verify sensitive values are NOT in file
    assert "sk-12345" not in content, "raw api_key leaked to file"
    assert "bearer-xyz" not in content, "raw token leaked to file"

    # Verify masked values ARE in file (check both with/without spaces for JSON formatting)
    assert "***" in content, "masked values should appear in file"

    # Verify non-sensitive data IS in file
    assert "/users" in content, "endpoint should be in file"


@pytest.mark.asyncio
@pytest.mark.security
async def test_redaction_reaches_http_sink() -> None:
    """Verify redacted data appears in HTTP request body.

    This test uses a capturing sender to verify that:
    1. Sensitive fields are masked in the HTTP body
    2. Raw secrets never appear in the request
    """
    import httpx

    from fapilog.plugins.sinks.http_client import (
        AsyncHttpSender,
        HttpSink,
    )

    class CapturingHttpSender(AsyncHttpSender):
        """Test double that captures all requests instead of sending them."""

        def __init__(self) -> None:
            self.captured: list[dict[str, Any]] = []
            # Don't call super().__init__ - we don't need a real pool

        async def post(
            self,
            url: str,
            *,
            json: Any | None = None,
            content: bytes | None = None,
            headers: Any = None,
        ) -> httpx.Response:
            if json is not None:
                if isinstance(json, list):
                    self.captured.extend(json)
                else:
                    self.captured.append(json)
            return httpx.Response(200)

    capturing_sender = CapturingHttpSender()

    # Create HTTP sink with capturing sender
    sink = HttpSink(
        config={
            "endpoint": "https://logs.example.com/ingest",
            "batch_size": 1,
        },
        sender=capturing_sender,
    )
    await sink.start()

    try:
        # Create redactor (v1.1 schema uses data.* paths)
        redactor = FieldMaskRedactor(
            config={
                "fields_to_mask": ["data.password", "data.secret"],
            }
        )

        logger = get_logger(name="redaction-http-test")
        logger._sink_write = sink.write  # type: ignore[attr-defined]
        logger._redactors = cast(list[BaseRedactor], [redactor])

        logger.info("login", username="bob", password="hunter2", secret="abc123")

        await logger.stop_and_drain()
    finally:
        await sink.stop()

    # Verify the captured HTTP request body
    assert len(capturing_sender.captured) == 1, "Expected 1 captured request"

    sent_event = capturing_sender.captured[0]
    data = sent_event.get("data", {})
    assert data.get("password") == "***", "password should be masked in HTTP body"
    assert data.get("secret") == "***", "secret should be masked in HTTP body"
    assert data.get("username") == "bob", "username should not be masked"

    # Verify raw secrets never sent
    all_content = json.dumps(capturing_sender.captured)
    assert "hunter2" not in all_content, "raw password leaked to HTTP"
    assert "abc123" not in all_content, "raw secret leaked to HTTP"


def _pg_env(key: str, default: str) -> str:
    return os.getenv(f"FAPILOG_POSTGRES__{key}", default)


@pytest.fixture
async def redaction_postgres_pool():
    """Create a fresh connection pool for redaction tests."""
    pytest.importorskip("asyncpg")
    import asyncpg

    try:
        pool = await asyncpg.create_pool(
            host=_pg_env("HOST", "localhost"),
            port=int(_pg_env("PORT", "5432")),
            database=_pg_env("DATABASE", "fapilog_test"),
            user=_pg_env("USER", "fapilog"),
            password=_pg_env("PASSWORD", "fapilog"),
        )
    except Exception as exc:
        pytest.skip(f"PostgreSQL not available: {exc}")
    else:
        yield pool
        await pool.close()


@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.postgres
async def test_redaction_reaches_postgres_sink(redaction_postgres_pool: Any) -> None:
    """Verify redacted data appears in PostgreSQL rows.

    This test queries the actual database to verify that:
    1. Sensitive fields are masked IN THE DATABASE
    2. Raw secrets are never stored
    """
    from fapilog.plugins.sinks.contrib.postgres import PostgresSink, PostgresSinkConfig

    # Clean up any existing table first
    async with redaction_postgres_pool.acquire() as conn:
        await conn.execute("DROP TABLE IF EXISTS public.redaction_test_logs")

    # Let the sink create its own table with proper schema
    sink = PostgresSink(
        PostgresSinkConfig(
            host=_pg_env("HOST", "localhost"),
            port=int(_pg_env("PORT", "5432")),
            database=_pg_env("DATABASE", "fapilog_test"),
            user=_pg_env("USER", "fapilog"),
            password=_pg_env("PASSWORD", "fapilog"),
            table_name="redaction_test_logs",
            batch_size=1,
            create_table=True,
        )
    )
    await sink.start()

    try:
        # Create redactor (v1.1 schema uses data.* paths)
        redactor = FieldMaskRedactor(
            config={
                "fields_to_mask": ["data.password", "data.credit_card"],
            }
        )

        logger = get_logger(name="redaction-postgres-test")
        logger._sink_write = sink.write  # type: ignore[attr-defined]
        logger._redactors = cast(list[BaseRedactor], [redactor])

        logger.info(
            "payment",
            user_id="u-123",
            password="secret",
            credit_card="4111111111111111",
            amount=99.99,
        )

        await logger.stop_and_drain()
    finally:
        await sink.stop()

    # Query the database directly - sink stores full event in 'event' JSONB column
    async with redaction_postgres_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM public.redaction_test_logs WHERE message = 'payment'"
        )

    assert row is not None, "No row found in database"  # noqa: WA003

    # Parse the 'event' JSONB column (sink's schema uses 'event')
    event_data = row["event"]
    if isinstance(event_data, str):
        event_data = json.loads(event_data)

    # Check in data since that's where fields are stored (v1.1 schema)
    data = event_data.get("data", {})

    # Verify sensitive fields are masked IN THE DATABASE
    assert data.get("password") == "***", "password should be masked in DB"
    assert data.get("credit_card") == "***", "credit_card should be masked in DB"

    # Verify non-sensitive fields are NOT masked
    # user_id is a context field in v1.1 schema, so it's in context not data
    context = event_data.get("context", {})
    assert context.get("user_id") == "u-123", "user_id should not be masked"
    assert data.get("amount") == 99.99, "amount should not be masked"

    # Verify raw secret never stored
    full_row_str = str(row)
    assert "4111111111111111" not in full_row_str, "raw credit_card leaked to DB"
    assert '"secret"' not in full_row_str or "***" in full_row_str, (
        "raw password may have leaked"
    )

    # Cleanup
    async with redaction_postgres_pool.acquire() as conn:
        await conn.execute("DROP TABLE IF EXISTS public.redaction_test_logs")


@pytest.mark.asyncio
@pytest.mark.security
async def test_redaction_applies_to_all_log_levels() -> None:
    """Verify redaction is applied regardless of log level.

    This test verifies that debug, info, warning, error, and exception
    log calls all apply redaction correctly.
    """
    collected: list[dict[str, Any]] = []

    async def collecting_sink(event: dict[str, Any]) -> None:
        collected.append(dict(event))

    redactor = FieldMaskRedactor(
        config={
            "fields_to_mask": ["data.secret"],
        }
    )

    logger = get_logger(name="redaction-levels-test")
    logger._sink_write = collecting_sink  # type: ignore[attr-defined]
    logger._redactors = cast(list[BaseRedactor], [redactor])

    logger.debug("debug-msg", secret="debug-secret")
    logger.info("info-msg", secret="info-secret")
    logger.warning("warning-msg", secret="warning-secret")
    logger.error("error-msg", secret="error-secret")

    try:
        raise ValueError("test error")
    except ValueError:
        logger.exception("exception-msg", secret="exception-secret")

    await logger.stop_and_drain()

    # Filter to only our test messages
    test_events = [e for e in collected if e.get("message", "").endswith("-msg")]

    # Verify we got events (at least info and above based on default log level)
    assert len(test_events) >= 4, f"Expected at least 4 events, got {len(test_events)}"

    # All captured events should have masked secret in data (v1.1 schema)
    for event in test_events:
        data = event.get("data", {})
        assert data.get("secret") == "***", (
            f"Event {event['message']} has unmasked secret"
        )

    # Verify none of the raw secrets appear
    all_content = json.dumps(collected)
    assert "debug-secret" not in all_content, "debug-secret leaked"
    assert "info-secret" not in all_content, "info-secret leaked"
    assert "warning-secret" not in all_content, "warning-secret leaked"
    assert "error-secret" not in all_content, "error-secret leaked"
    assert "exception-secret" not in all_content, "exception-secret leaked"


@pytest.mark.asyncio
@pytest.mark.security
async def test_redaction_happens_before_serialization() -> None:
    """Verify redaction occurs before JSON serialization.

    This test captures the payload at sink time and verifies that
    redaction has already been applied.
    """
    captured_payloads: list[dict[str, Any]] = []

    async def capturing_sink(event: dict[str, Any]) -> None:
        # Capture a deep copy to preserve the state at sink time
        import copy

        captured_payloads.append(copy.deepcopy(event))

    redactor = FieldMaskRedactor(
        config={
            "fields_to_mask": ["data.password"],
        }
    )

    logger = get_logger(name="redaction-order-test")
    logger._sink_write = capturing_sink  # type: ignore[attr-defined]
    logger._redactors = cast(list[BaseRedactor], [redactor])

    logger.info("login", password="supersecret")

    await logger.stop_and_drain()

    # The payload at sink should already have masked value
    assert len(captured_payloads) == 1, "Expected 1 captured payload"

    payload = captured_payloads[0]
    data = payload.get("data", {})

    # Verify redaction occurred BEFORE reaching sink
    assert data.get("password") == "***", "password should be masked at sink time"
    assert "supersecret" not in str(payload), "supersecret appears in payload"

    # Verify the unmasked value never reaches the sink
    all_content = json.dumps(captured_payloads)
    assert "supersecret" not in all_content, "supersecret leaked to sink"
