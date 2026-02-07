"""Unit tests for FieldBlockerRedactor (Story 4.69)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from fapilog.plugins.redactors.field_blocker import (
    DEFAULT_BLOCKED_FIELDS,
    FieldBlockerRedactor,
)


@pytest.fixture
def redactor() -> FieldBlockerRedactor:
    """Redactor with explicit blocklist for deterministic tests."""
    return FieldBlockerRedactor(
        config={
            "blocked_fields": ["body", "request_body", "response_body", "payload"],
        }
    )


# --- AC1: Blocked Fields Are Replaced ---


@pytest.mark.asyncio
async def test_blocked_field_replaced(redactor: FieldBlockerRedactor) -> None:
    event = {
        "data": {
            "request_body": '{"email": "alice@example.com", "password": "secret"}',
            "status_code": 200,
        }
    }
    result = await redactor.redact(event)
    assert result["data"]["request_body"] == "[REDACTED:HIGH_RISK_FIELD]"
    assert result["data"]["status_code"] == 200


@pytest.mark.asyncio
async def test_multiple_blocked_fields_replaced(redactor: FieldBlockerRedactor) -> None:
    event = {
        "data": {
            "body": "some content",
            "payload": {"nested": "data"},
            "safe_field": "keep",
        }
    }
    result = await redactor.redact(event)
    assert result["data"]["body"] == "[REDACTED:HIGH_RISK_FIELD]"
    assert result["data"]["payload"] == "[REDACTED:HIGH_RISK_FIELD]"
    assert result["data"]["safe_field"] == "keep"


# --- AC2: Nested Blocked Fields Are Caught ---


@pytest.mark.asyncio
async def test_nested_blocked_field_caught(redactor: FieldBlockerRedactor) -> None:
    event = {
        "data": {
            "http": {
                "response_body": "<html>...PII...</html>",
                "headers": {"content-type": "text/html"},
            }
        }
    }
    result = await redactor.redact(event)
    assert result["data"]["http"]["response_body"] == "[REDACTED:HIGH_RISK_FIELD]"
    assert result["data"]["http"]["headers"]["content-type"] == "text/html"


@pytest.mark.asyncio
async def test_deeply_nested_blocked_field() -> None:
    redactor = FieldBlockerRedactor(config={"blocked_fields": ["secret"]})
    event = {"data": {"level1": {"level2": {"level3": {"secret": "value"}}}}}
    result = await redactor.redact(event)
    assert (
        result["data"]["level1"]["level2"]["level3"]["secret"]
        == "[REDACTED:HIGH_RISK_FIELD]"
    )


# --- AC3: Policy Violation Diagnostic Emitted ---


@pytest.mark.asyncio
async def test_policy_violation_diagnostic(redactor: FieldBlockerRedactor) -> None:
    event = {"data": {"request_body": "sensitive"}}
    with patch("fapilog.plugins.redactors.field_blocker.diagnostics") as mock_diag:
        await redactor.redact(event)
        mock_diag.warn.assert_called_once_with(
            "redactor",
            "high-risk field blocked",
            field="request_body",
            path="data.request_body",
            policy_violation=True,
        )


@pytest.mark.asyncio
async def test_no_diagnostic_when_no_blocked_fields(
    redactor: FieldBlockerRedactor,
) -> None:
    event = {"data": {"safe_field": "value"}}
    with patch("fapilog.plugins.redactors.field_blocker.diagnostics") as mock_diag:
        await redactor.redact(event)
        mock_diag.warn.assert_not_called()


# --- AC4: Allowlist Overrides Blocklist ---


@pytest.mark.asyncio
async def test_allowlist_overrides_blocklist() -> None:
    redactor = FieldBlockerRedactor(
        config={
            "blocked_fields": ["body", "payload"],
            "allowed_fields": ["body"],
        }
    )
    event = {"data": {"body": "safe content", "payload": "unsafe"}}
    result = await redactor.redact(event)
    assert result["data"]["body"] == "safe content"
    assert result["data"]["payload"] == "[REDACTED:HIGH_RISK_FIELD]"


@pytest.mark.asyncio
async def test_allowlist_is_case_insensitive() -> None:
    redactor = FieldBlockerRedactor(
        config={
            "blocked_fields": ["body"],
            "allowed_fields": ["BODY"],
        }
    )
    event = {"data": {"body": "allowed"}}
    result = await redactor.redact(event)
    assert result["data"]["body"] == "allowed"


# --- Default Blocklist Coverage ---


@pytest.mark.asyncio
async def test_default_blocklist_coverage() -> None:
    redactor = FieldBlockerRedactor()
    event = {"data": {field: f"value_{field}" for field in DEFAULT_BLOCKED_FIELDS}}
    result = await redactor.redact(event)
    for field in DEFAULT_BLOCKED_FIELDS:
        assert result["data"][field] == "[REDACTED:HIGH_RISK_FIELD]", (
            f"Default blocklist field '{field}' was not blocked"
        )


# --- Case-Insensitive Matching ---


@pytest.mark.asyncio
async def test_case_insensitive_matching() -> None:
    redactor = FieldBlockerRedactor(config={"blocked_fields": ["request_body"]})
    event = {"data": {"Request_Body": "sensitive", "REQUEST_BODY": "also sensitive"}}
    result = await redactor.redact(event)
    assert result["data"]["Request_Body"] == "[REDACTED:HIGH_RISK_FIELD]"
    assert result["data"]["REQUEST_BODY"] == "[REDACTED:HIGH_RISK_FIELD]"


# --- Guardrails ---


@pytest.mark.asyncio
async def test_max_depth_guardrail_warn() -> None:
    redactor = FieldBlockerRedactor(
        config={
            "blocked_fields": ["secret"],
            "max_depth": 2,
            "on_guardrail_exceeded": "warn",
        }
    )
    event = {"data": {"l1": {"l2": {"l3": {"secret": "deep"}}}}}
    with patch("fapilog.plugins.redactors.field_blocker.diagnostics") as mock_diag:
        result = await redactor.redact(event)
        # Secret is beyond max_depth=2, should not be blocked
        assert result["data"]["l1"]["l2"]["l3"]["secret"] == "deep"
        mock_diag.warn.assert_called()


@pytest.mark.asyncio
async def test_max_depth_guardrail_drop() -> None:
    redactor = FieldBlockerRedactor(
        config={
            "blocked_fields": ["secret"],
            "max_depth": 2,
            "on_guardrail_exceeded": "drop",
        }
    )
    event = {"data": {"l1": {"l2": {"l3": {"secret": "deep"}}}, "safe": "ok"}}
    result = await redactor.redact(event)
    # On drop, return original event unchanged
    assert result["data"]["l1"]["l2"]["l3"]["secret"] == "deep"
    assert result["data"]["safe"] == "ok"


@pytest.mark.asyncio
async def test_max_keys_scanned_guardrail() -> None:
    redactor = FieldBlockerRedactor(
        config={
            "blocked_fields": ["target"],
            "max_keys_scanned": 3,
            "on_guardrail_exceeded": "warn",
        }
    )
    event = {"a": 1, "b": 2, "c": 3, "d": 4, "target": "should_not_reach"}
    with patch("fapilog.plugins.redactors.field_blocker.diagnostics") as mock_diag:
        await redactor.redact(event)
        mock_diag.warn.assert_called()


# --- Core Guardrails ("more restrictive wins") ---


@pytest.mark.asyncio
async def test_core_guardrails_more_restrictive_wins() -> None:
    # Plugin says depth=16, core says depth=3 -> effective is 3
    redactor = FieldBlockerRedactor(
        config={"blocked_fields": ["secret"], "max_depth": 16},
        core_max_depth=3,
    )
    event = {"d1": {"d2": {"d3": {"d4": {"secret": "deep"}}}}}
    result = await redactor.redact(event)
    # depth 4 exceeds effective max of 3; secret should survive
    assert result["d1"]["d2"]["d3"]["d4"]["secret"] == "deep"


@pytest.mark.asyncio
async def test_core_guardrails_plugin_more_restrictive() -> None:
    # Plugin says depth=2, core says depth=10 -> effective is 2
    redactor = FieldBlockerRedactor(
        config={"blocked_fields": ["secret"], "max_depth": 2},
        core_max_depth=10,
    )
    event = {"d1": {"d2": {"d3": {"secret": "deep"}}}}
    result = await redactor.redact(event)
    # depth 3 exceeds effective max of 2; secret should survive
    assert result["d1"]["d2"]["d3"]["secret"] == "deep"


# --- Guardrail Exceeded: warn vs drop ---


@pytest.mark.asyncio
async def test_guardrail_exceeded_warn_continues_partial() -> None:
    redactor = FieldBlockerRedactor(
        config={
            "blocked_fields": ["secret"],
            "max_depth": 1,
            "on_guardrail_exceeded": "warn",
        }
    )
    # secret at depth 0 should be caught, nested secret at depth 2 should not
    event = {"secret": "top", "nested": {"deep": {"secret": "unreachable"}}}
    result = await redactor.redact(event)
    assert result["secret"] == "[REDACTED:HIGH_RISK_FIELD]"


@pytest.mark.asyncio
async def test_guardrail_exceeded_drop_returns_original() -> None:
    redactor = FieldBlockerRedactor(
        config={
            "blocked_fields": ["secret"],
            "max_depth": 1,
            "on_guardrail_exceeded": "drop",
        }
    )
    event = {"secret": "top", "nested": {"deep": {"secret": "unreachable"}}}
    result = await redactor.redact(event)
    # Drop returns original event entirely
    assert result == event


@pytest.mark.asyncio
async def test_guardrail_exceeded_drop_inside_list_traversal() -> None:
    redactor = FieldBlockerRedactor(
        config={
            "blocked_fields": ["secret"],
            "max_depth": 1,
            "on_guardrail_exceeded": "drop",
        }
    )
    # List items with nested dicts that exceed max_depth trigger drop inside list
    event = {"items": [{"nested": {"secret": "deep"}}]}
    result = await redactor.redact(event)
    assert result == event


# --- Custom Replacement String ---


@pytest.mark.asyncio
async def test_custom_replacement_string() -> None:
    redactor = FieldBlockerRedactor(
        config={
            "blocked_fields": ["body"],
            "replacement": "[BLOCKED]",
        }
    )
    event = {"data": {"body": "content"}}
    result = await redactor.redact(event)
    assert result["data"]["body"] == "[BLOCKED]"


# --- Health Check ---


@pytest.mark.asyncio
async def test_health_check_passes() -> None:
    redactor = FieldBlockerRedactor()
    assert await redactor.health_check() is True


@pytest.mark.asyncio
async def test_health_check_with_empty_blocklist() -> None:
    redactor = FieldBlockerRedactor(config={"blocked_fields": []})
    assert await redactor.health_check() is True


# --- Lifecycle ---


@pytest.mark.asyncio
async def test_start_stop_are_noops() -> None:
    redactor = FieldBlockerRedactor()
    await redactor.start()
    await redactor.stop()
    # No exception means success


# --- Event Immutability ---


@pytest.mark.asyncio
async def test_top_level_dict_not_same_object(redactor: FieldBlockerRedactor) -> None:
    """Redactor returns a new top-level dict (shallow copy).

    Deep copy is the caller's responsibility (redact_in_order does this).
    """
    event = {"data": {"request_body": "sensitive"}}
    result = await redactor.redact(event)
    assert result is not event
    assert result["data"]["request_body"] == "[REDACTED:HIGH_RISK_FIELD]"


# --- Edge Cases ---


@pytest.mark.asyncio
async def test_empty_event() -> None:
    redactor = FieldBlockerRedactor()
    result = await redactor.redact({})
    assert result == {}


@pytest.mark.asyncio
async def test_event_with_list_values(redactor: FieldBlockerRedactor) -> None:
    event = {"data": {"items": [{"body": "in list"}]}}
    result = await redactor.redact(event)
    assert result["data"]["items"][0]["body"] == "[REDACTED:HIGH_RISK_FIELD]"


@pytest.mark.asyncio
async def test_blocked_field_with_none_value() -> None:
    redactor = FieldBlockerRedactor(config={"blocked_fields": ["body"]})
    event = {"data": {"body": None}}
    result = await redactor.redact(event)
    assert result["data"]["body"] == "[REDACTED:HIGH_RISK_FIELD]"
