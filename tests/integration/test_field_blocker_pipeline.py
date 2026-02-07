"""Integration tests for field_blocker redactor through the full pipeline.

Story 4.69: Verifies that:
- Builder API configures field blocking (AC5)
- Blocked fields never reach sink output (AC6)
"""

from __future__ import annotations

import json
from typing import Any, cast

import pytest

from fapilog.builder import LoggerBuilder
from fapilog.core.envelope import build_envelope
from fapilog.core.serialization import serialize_envelope
from fapilog.plugins.redactors import redact_in_order
from fapilog.plugins.redactors.field_blocker import FieldBlockerRedactor

pytestmark = pytest.mark.integration


class TestBuilderWithBlockFields:
    """AC5: Builder provides a way to configure field blocking."""

    def test_builder_adds_field_blocker_to_redactors(self) -> None:
        builder = LoggerBuilder()
        builder.with_redaction(block_fields=["body", "payload"])
        config = builder._config

        redactors = config["core"]["redactors"]
        assert "field_blocker" in redactors

        blocker_cfg = config["redactor_config"]["field_blocker"]
        assert "body" in blocker_cfg["blocked_fields"]
        assert "payload" in blocker_cfg["blocked_fields"]

    def test_builder_block_fields_additive(self) -> None:
        builder = LoggerBuilder()
        builder.with_redaction(block_fields=["body"])
        builder.with_redaction(block_fields=["payload"])
        config = builder._config

        blocker_cfg = config["redactor_config"]["field_blocker"]
        assert "body" in blocker_cfg["blocked_fields"]
        assert "payload" in blocker_cfg["blocked_fields"]

    def test_builder_block_fields_no_duplicates(self) -> None:
        builder = LoggerBuilder()
        builder.with_redaction(block_fields=["body"])
        builder.with_redaction(block_fields=["body"])
        config = builder._config

        blocker_cfg = config["redactor_config"]["field_blocker"]
        assert blocker_cfg["blocked_fields"].count("body") == 1

    def test_builder_block_fields_replace_mode(self) -> None:
        builder = LoggerBuilder()
        builder.with_redaction(block_fields=["body"])
        builder.with_redaction(block_fields=["payload"], replace=True)
        config = builder._config

        blocker_cfg = config["redactor_config"]["field_blocker"]
        assert blocker_cfg["blocked_fields"] == ["payload"]


class TestBlockedFieldNeverReachesSink:
    """AC6: Blocked field produces sink output without the original value."""

    @pytest.mark.asyncio
    async def test_blocked_field_absent_from_serialized_output(self) -> None:
        """Full pipeline: build → redact → serialize. Blocked value must not appear."""
        original_body = '{"email": "alice@example.com", "ssn": "123-45-6789"}'

        envelope = build_envelope(
            level="INFO",
            message="api request",
            extra={"request_body": original_body, "method": "POST", "path": "/api"},
        )

        blocker = FieldBlockerRedactor(
            config={"blocked_fields": ["request_body"]},
        )
        redacted = await redact_in_order(cast(dict[str, Any], envelope), [blocker])

        serialized = serialize_envelope(redacted)
        output = (
            serialized.data.decode("utf-8")
            if isinstance(serialized.data, bytes)
            else serialized.data
        )

        # Original value must not appear in output
        assert original_body not in output

        # Replacement marker must be present
        parsed = json.loads(output)
        assert parsed["log"]["data"]["request_body"] == "[REDACTED:HIGH_RISK_FIELD]"

        # Non-blocked fields preserved
        assert parsed["log"]["data"]["method"] == "POST"
        assert parsed["log"]["data"]["path"] == "/api"

    @pytest.mark.asyncio
    async def test_nested_blocked_field_absent_from_output(self) -> None:
        """Blocked field nested in event tree still gets caught."""
        original_payload = "sensitive-data-here"

        envelope = build_envelope(
            level="INFO",
            message="webhook",
            extra={"http": {"payload": original_payload, "status": 200}},
        )

        blocker = FieldBlockerRedactor(
            config={"blocked_fields": ["payload"]},
        )
        redacted = await redact_in_order(cast(dict[str, Any], envelope), [blocker])

        serialized = serialize_envelope(redacted)
        output = (
            serialized.data.decode("utf-8")
            if isinstance(serialized.data, bytes)
            else serialized.data
        )

        assert original_payload not in output
        parsed = json.loads(output)
        assert parsed["log"]["data"]["http"]["payload"] == "[REDACTED:HIGH_RISK_FIELD]"
        assert parsed["log"]["data"]["http"]["status"] == 200
