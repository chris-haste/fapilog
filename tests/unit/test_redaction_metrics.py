"""Tests for redaction operational metrics (Story 4.71).

Validates the three new counters:
- fapilog_redacted_fields_total
- fapilog_policy_violations_total
- fapilog_sensitive_fields_total
"""

from __future__ import annotations

import pytest

from fapilog.metrics.metrics import MetricsCollector
from fapilog.plugins.redactors import redact_in_order
from fapilog.plugins.redactors.field_blocker import FieldBlockerRedactor
from fapilog.plugins.redactors.field_mask import FieldMaskRedactor
from fapilog.plugins.redactors.regex_mask import RegexMaskRedactor
from fapilog.plugins.redactors.url_credentials import UrlCredentialsRedactor


@pytest.mark.asyncio
async def test_redacted_fields_counter_increments() -> None:
    mc = MetricsCollector(enabled=True)
    await mc.record_redacted_fields(3)
    await mc.record_redacted_fields(2)

    reg = mc.registry
    assert reg is not None  # noqa: WA003
    assert reg.get_sample_value("fapilog_redacted_fields_total") == 5.0


@pytest.mark.asyncio
async def test_policy_violations_counter_increments() -> None:
    mc = MetricsCollector(enabled=True)
    await mc.record_policy_violations(1)
    await mc.record_policy_violations(4)

    reg = mc.registry
    assert reg is not None  # noqa: WA003
    assert reg.get_sample_value("fapilog_policy_violations_total") == 5.0


@pytest.mark.asyncio
async def test_sensitive_fields_counter_increments() -> None:
    mc = MetricsCollector(enabled=True)
    await mc.record_sensitive_fields(2)
    await mc.record_sensitive_fields(1)

    reg = mc.registry
    assert reg is not None  # noqa: WA003
    assert reg.get_sample_value("fapilog_sensitive_fields_total") == 3.0


@pytest.mark.asyncio
async def test_counters_zero_when_unused() -> None:
    mc = MetricsCollector(enabled=True)

    reg = mc.registry
    assert reg is not None  # noqa: WA003
    assert reg.get_sample_value("fapilog_redacted_fields_total") == 0.0
    assert reg.get_sample_value("fapilog_policy_violations_total") == 0.0
    assert reg.get_sample_value("fapilog_sensitive_fields_total") == 0.0


@pytest.mark.asyncio
async def test_metrics_disabled_noop() -> None:
    mc = MetricsCollector(enabled=False)
    # Should not raise
    await mc.record_redacted_fields(5)
    await mc.record_policy_violations(3)
    await mc.record_sensitive_fields(2)
    # Registry should not exist when disabled
    assert mc.registry is None


@pytest.mark.asyncio
async def test_cleanup_clears_plugin_stats_not_counters() -> None:
    mc = MetricsCollector(enabled=True)
    await mc.record_redacted_fields(10)
    mc.cleanup()
    # Prometheus counters are not reset by cleanup (they are append-only).
    # cleanup() clears plugin_stats only.
    reg = mc.registry
    assert reg is not None  # noqa: WA003
    assert reg.get_sample_value("fapilog_redacted_fields_total") == 10.0


# --- Redactor counting tests ---


@pytest.mark.asyncio
async def test_field_mask_tracks_redacted_count() -> None:
    r = FieldMaskRedactor(config={"fields_to_mask": ["password", "secret"]})
    event = {"password": "hunter2", "secret": "abc", "safe": "ok"}
    result = await r.redact(event)
    assert result["password"] == "***"
    assert result["secret"] == "***"
    assert result["safe"] == "ok"
    assert r.last_redacted_count == 2


@pytest.mark.asyncio
async def test_field_mask_count_zero_when_no_match() -> None:
    r = FieldMaskRedactor(config={"fields_to_mask": ["password"]})
    event = {"username": "alice"}
    await r.redact(event)
    assert r.last_redacted_count == 0


@pytest.mark.asyncio
async def test_field_mask_count_skips_already_masked() -> None:
    r = FieldMaskRedactor(config={"fields_to_mask": ["password"]})
    event = {"password": "***"}
    await r.redact(event)
    assert r.last_redacted_count == 0


@pytest.mark.asyncio
async def test_regex_mask_tracks_redacted_count() -> None:
    r = RegexMaskRedactor(config={"patterns": [r"data\.secret"]})
    event = {"data": {"secret": "value", "public": "ok"}}
    result = await r.redact(event)
    assert result["data"]["secret"] == "***"
    assert result["data"]["public"] == "ok"
    assert r.last_redacted_count == 1


@pytest.mark.asyncio
async def test_regex_mask_count_zero_when_no_match() -> None:
    r = RegexMaskRedactor(config={"patterns": [r"data\.secret"]})
    event = {"data": {"public": "ok"}}
    await r.redact(event)
    assert r.last_redacted_count == 0


@pytest.mark.asyncio
async def test_url_credentials_tracks_redacted_count() -> None:
    r = UrlCredentialsRedactor()
    event = {
        "url": "https://user:pass@example.com/path",
        "safe_url": "https://example.com/page",
    }
    result = await r.redact(event)
    assert "user" not in result["url"]
    assert result["safe_url"] == "https://example.com/page"
    assert r.last_redacted_count == 1


@pytest.mark.asyncio
async def test_url_credentials_count_zero_when_no_credentials() -> None:
    r = UrlCredentialsRedactor()
    event = {"url": "https://example.com/page"}
    await r.redact(event)
    assert r.last_redacted_count == 0


@pytest.mark.asyncio
async def test_field_blocker_tracks_policy_violations() -> None:
    r = FieldBlockerRedactor(
        config={"blocked_fields": ["body", "payload"], "allowed_fields": []}
    )
    event = {"body": "raw data", "payload": "stuff", "safe": "ok"}
    result = await r.redact(event)
    assert result["body"] == "[REDACTED:HIGH_RISK_FIELD]"
    assert result["payload"] == "[REDACTED:HIGH_RISK_FIELD]"
    assert result["safe"] == "ok"
    assert r.last_policy_violations == 2


@pytest.mark.asyncio
async def test_field_blocker_zero_violations_when_no_match() -> None:
    r = FieldBlockerRedactor(config={"blocked_fields": ["body"], "allowed_fields": []})
    event = {"safe": "ok"}
    await r.redact(event)
    assert r.last_policy_violations == 0


# --- redact_in_order integration tests ---


@pytest.mark.asyncio
async def test_redact_in_order_records_redacted_fields_metric() -> None:
    mc = MetricsCollector(enabled=True)
    r = FieldMaskRedactor(config={"fields_to_mask": ["password"]})
    event = {"password": "secret", "user": "alice"}

    await redact_in_order(event, [r], metrics=mc)

    reg = mc.registry
    assert reg is not None  # noqa: WA003
    assert reg.get_sample_value("fapilog_redacted_fields_total") == 1.0


@pytest.mark.asyncio
async def test_redact_in_order_records_policy_violations_metric() -> None:
    mc = MetricsCollector(enabled=True)
    r = FieldBlockerRedactor(
        config={"blocked_fields": ["body", "payload"], "allowed_fields": []}
    )
    event = {"body": "raw", "payload": "data", "ok": "fine"}

    await redact_in_order(event, [r], metrics=mc)

    reg = mc.registry
    assert reg is not None  # noqa: WA003
    assert reg.get_sample_value("fapilog_policy_violations_total") == 2.0


@pytest.mark.asyncio
async def test_redact_in_order_aggregates_across_redactors() -> None:
    mc = MetricsCollector(enabled=True)
    fm = FieldMaskRedactor(config={"fields_to_mask": ["password"]})
    rm = RegexMaskRedactor(config={"patterns": [r"data\.secret"]})
    event = {"password": "hunter2", "data": {"secret": "val"}}

    await redact_in_order(event, [fm, rm], metrics=mc)

    reg = mc.registry
    assert reg is not None  # noqa: WA003
    # 1 from field_mask + 1 from regex_mask
    assert reg.get_sample_value("fapilog_redacted_fields_total") == 2.0
