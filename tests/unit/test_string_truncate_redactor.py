"""Unit tests for StringTruncateRedactor (Story 10.54)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from fapilog.plugins.redactors.string_truncate import (
    StringTruncateRedactor,
)


@pytest.fixture
def redactor() -> StringTruncateRedactor:
    """Redactor with 256-char threshold for deterministic tests."""
    return StringTruncateRedactor(config={"max_string_length": 256})


# --- AC1: Long Strings Are Truncated ---


@pytest.mark.asyncio
async def test_long_string_truncated(redactor: StringTruncateRedactor) -> None:
    event = {"data": {"description": "x" * 1000}}
    result = await redactor.redact(event)
    assert len(result["data"]["description"]) == 256 + len("[truncated]")
    assert result["data"]["description"].endswith("[truncated]")
    assert result["data"]["description"].startswith("x" * 256)


@pytest.mark.asyncio
async def test_string_at_exact_threshold_untouched(
    redactor: StringTruncateRedactor,
) -> None:
    event = {"data": {"name": "x" * 256}}
    result = await redactor.redact(event)
    assert result["data"]["name"] == "x" * 256


# --- AC2: Short Strings Are Untouched ---


@pytest.mark.asyncio
async def test_short_string_untouched(redactor: StringTruncateRedactor) -> None:
    event = {"data": {"name": "Alice"}}
    result = await redactor.redact(event)
    assert result["data"]["name"] == "Alice"


# --- AC3: Nested Strings Are Truncated ---


@pytest.mark.asyncio
async def test_nested_string_truncated(redactor: StringTruncateRedactor) -> None:
    event = {"data": {"user": {"bio": "x" * 1000}}}
    result = await redactor.redact(event)
    assert result["data"]["user"]["bio"].endswith("[truncated]")
    assert len(result["data"]["user"]["bio"]) == 256 + len("[truncated]")


@pytest.mark.asyncio
async def test_strings_in_list_truncated(redactor: StringTruncateRedactor) -> None:
    event = {"data": {"tags": ["short", "x" * 1000]}}
    result = await redactor.redact(event)
    assert result["data"]["tags"][0] == "short"
    assert result["data"]["tags"][1].endswith("[truncated]")


# --- AC4: Truncation Diagnostic Emitted ---


@pytest.mark.asyncio
async def test_truncation_diagnostic_emitted(
    redactor: StringTruncateRedactor,
) -> None:
    event = {"data": {"description": "x" * 1000}}
    with patch("fapilog.plugins.redactors.string_truncate.diagnostics") as mock_diag:
        await redactor.redact(event)
        mock_diag.warn.assert_called_once_with(
            "redactor",
            "string field truncated",
            path="data.description",
            original_length=1000,
            truncated_to=256,
        )


@pytest.mark.asyncio
async def test_no_diagnostic_when_no_truncation(
    redactor: StringTruncateRedactor,
) -> None:
    event = {"data": {"name": "Alice"}}
    with patch("fapilog.plugins.redactors.string_truncate.diagnostics") as mock_diag:
        await redactor.redact(event)
        mock_diag.warn.assert_not_called()


# --- AC5: Disabled by Default ---


@pytest.mark.asyncio
async def test_disabled_by_default() -> None:
    redactor = StringTruncateRedactor()
    event = {"data": {"huge": "x" * 100000}}
    result = await redactor.redact(event)
    assert result["data"]["huge"] == "x" * 100000


# --- AC6: Builder Integration ---


def test_builder_integration() -> None:
    from fapilog.builder import LoggerBuilder

    builder = LoggerBuilder().with_redaction(max_string_length=4096)
    config = builder._config
    assert "string_truncate" in config["core"]["redactors"]
    assert config["redactor_config"]["string_truncate"]["max_string_length"] == 4096


# --- Guardrails ---


@pytest.mark.asyncio
async def test_max_depth_guardrail() -> None:
    redactor = StringTruncateRedactor(config={"max_string_length": 10, "max_depth": 2})
    # Build event deeper than max_depth
    event = {"data": {"level1": {"level2": {"deep_value": "x" * 100}}}}
    with patch("fapilog.plugins.redactors.string_truncate.diagnostics") as mock_diag:
        result = await redactor.redact(event)
    # Value beyond max_depth should NOT be truncated
    assert result["data"]["level1"]["level2"]["deep_value"] == "x" * 100
    mock_diag.warn.assert_called()


@pytest.mark.asyncio
async def test_max_keys_scanned_guardrail() -> None:
    redactor = StringTruncateRedactor(
        config={"max_string_length": 10, "max_keys_scanned": 3}
    )
    event = {"a": "short", "b": "short", "c": "short", "d": "x" * 100}
    with patch("fapilog.plugins.redactors.string_truncate.diagnostics") as mock_diag:
        result = await redactor.redact(event)
    # After scanning 3 keys, the 4th should not be processed
    assert result["d"] == "x" * 100
    mock_diag.warn.assert_called()


@pytest.mark.asyncio
async def test_core_guardrails_more_restrictive_wins() -> None:
    redactor = StringTruncateRedactor(
        config={"max_string_length": 10, "max_depth": 16},
        core_max_depth=3,
    )
    assert redactor._max_depth == 3


# --- Non-string values ---


@pytest.mark.asyncio
async def test_non_string_values_untouched(redactor: StringTruncateRedactor) -> None:
    event = {
        "data": {
            "count": 42,
            "active": True,
            "ratio": 3.14,
            "empty": None,
        }
    }
    result = await redactor.redact(event)
    assert result["data"]["count"] == 42
    assert result["data"]["active"] is True
    assert result["data"]["ratio"] == 3.14
    assert result["data"]["empty"] is None


# --- Metrics tracking ---


@pytest.mark.asyncio
async def test_last_redacted_count_tracked(redactor: StringTruncateRedactor) -> None:
    event = {"data": {"a": "x" * 1000, "b": "x" * 1000, "c": "short"}}
    await redactor.redact(event)
    assert redactor.last_redacted_count == 2


@pytest.mark.asyncio
async def test_original_event_not_mutated(redactor: StringTruncateRedactor) -> None:
    original_value = "x" * 1000
    event = {"data": {"description": original_value}}
    await redactor.redact(event)
    assert event["data"]["description"] == original_value


# --- core_max_keys_scanned guardrail ---


@pytest.mark.asyncio
async def test_core_max_keys_scanned_more_restrictive_wins() -> None:
    redactor = StringTruncateRedactor(
        config={"max_string_length": 10, "max_keys_scanned": 1000},
        core_max_keys_scanned=5,
    )
    assert redactor._max_scanned == 5


# --- on_guardrail_exceeded=drop ---


@pytest.mark.asyncio
async def test_guardrail_drop_returns_original_on_depth() -> None:
    redactor = StringTruncateRedactor(
        config={
            "max_string_length": 10,
            "max_depth": 1,
            "on_guardrail_exceeded": "drop",
        }
    )
    event = {"data": {"nested": {"deep": "x" * 100}}}
    result = await redactor.redact(event)
    # drop mode: return untouched copy of original event
    assert result["data"]["nested"]["deep"] == "x" * 100


@pytest.mark.asyncio
async def test_guardrail_drop_returns_original_on_keys_exceeded() -> None:
    redactor = StringTruncateRedactor(
        config={
            "max_string_length": 10,
            "max_keys_scanned": 1,
            "on_guardrail_exceeded": "drop",
        }
    )
    event = {"a": "short", "b": "x" * 100}
    result = await redactor.redact(event)
    # drop mode: return untouched copy of original
    assert result["b"] == "x" * 100


# --- Nested dicts in lists ---


@pytest.mark.asyncio
async def test_dict_nested_in_list_truncated(redactor: StringTruncateRedactor) -> None:
    event = {"data": {"items": [{"description": "x" * 1000}]}}
    result = await redactor.redact(event)
    assert result["data"]["items"][0]["description"].endswith("[truncated]")


# --- health_check ---


@pytest.mark.asyncio
async def test_health_check_returns_true(redactor: StringTruncateRedactor) -> None:
    assert await redactor.health_check() is True
