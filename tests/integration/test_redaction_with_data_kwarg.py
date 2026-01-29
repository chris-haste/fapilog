"""
Integration tests for redaction with data={} kwarg pattern (Story 10.40).

Verifies that fields passed via data={...} are correctly redacted,
ensuring the security footgun is fixed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fapilog import AsyncLoggerBuilder

pytestmark = [pytest.mark.integration, pytest.mark.security]


@pytest.mark.asyncio
async def test_redaction_works_with_data_dict_pattern(tmp_path: Path) -> None:
    """AC3: Fields in data={...} are correctly redacted.

    This was a security footgun: redaction configured for 'password'
    would look at data.password, but actual path was data.data.password.
    With flattening, redaction now works correctly.
    """
    logger = await (
        AsyncLoggerBuilder()
        .with_redaction(fields=["password"])
        .add_file(directory=str(tmp_path))
        .build_async()
    )

    # Using data={} pattern - the common way developers log structured data
    await logger.info(
        "Login attempt", data={"username": "alice", "password": "secret123"}
    )
    await logger.drain()

    # Read the output file
    log_files = list(tmp_path.glob("*.jsonl"))
    assert len(log_files) == 1, f"Expected 1 log file, found {len(log_files)}"

    content = log_files[0].read_text()

    # Password should be redacted - the secret value must NOT appear
    assert "secret123" not in content, "Password was not redacted!"

    # Parse and verify structure (output is wrapped in "log" key)
    log_entry = json.loads(content.strip())["log"]
    assert log_entry["data"]["password"] == "***"
    assert log_entry["data"]["username"] == "alice"


@pytest.mark.asyncio
async def test_full_pipeline_data_dict_to_file_sink(tmp_path: Path) -> None:
    """End-to-end test: data dict flows through full pipeline to file sink."""
    logger = await AsyncLoggerBuilder().add_file(directory=str(tmp_path)).build_async()

    # Log with data dict pattern
    await logger.info(
        "User action",
        data={"action": "click", "element": "button"},
        extra_field="additional",
    )
    await logger.drain()

    # Read and verify
    log_files = list(tmp_path.glob("*.jsonl"))
    assert len(log_files) == 1

    log_entry = json.loads(log_files[0].read_text().strip())["log"]

    # Data dict contents should be flattened
    assert log_entry["data"]["action"] == "click"
    assert log_entry["data"]["element"] == "button"
    # Extra field should also be in data
    assert log_entry["data"]["extra_field"] == "additional"


@pytest.mark.asyncio
async def test_multiple_sensitive_fields_redacted_via_data_dict(tmp_path: Path) -> None:
    """Multiple sensitive fields passed via data={} are all redacted."""
    logger = await (
        AsyncLoggerBuilder()
        .with_redaction(fields=["password", "ssn", "api_key"])
        .add_file(directory=str(tmp_path))
        .build_async()
    )

    await logger.info(
        "User registration",
        data={
            "username": "bob",
            "password": "supersecret",
            "ssn": "123-45-6789",
            "api_key": "sk-live-abc123",
        },
    )
    await logger.drain()

    content = (
        log_files[0].read_text()
        if (log_files := list(tmp_path.glob("*.jsonl")))
        else ""
    )
    log_entry = json.loads(content.strip())["log"]

    # All sensitive fields should be redacted
    assert log_entry["data"]["password"] == "***"
    assert log_entry["data"]["ssn"] == "***"
    assert log_entry["data"]["api_key"] == "***"
    # Non-sensitive field preserved
    assert log_entry["data"]["username"] == "bob"
