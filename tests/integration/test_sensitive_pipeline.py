"""Integration tests for sensitive container through the full pipeline.

Story 4.68: Verifies that sensitive data masked at envelope construction
time survives redaction and serialization without leaking original values.
"""

from __future__ import annotations

import json
from typing import Any, cast

import pytest

from fapilog.core.envelope import build_envelope
from fapilog.core.serialization import serialize_envelope
from fapilog.plugins.redactors import BaseRedactor, redact_in_order

pytestmark = pytest.mark.integration


class _NoopRedactor(BaseRedactor):
    """Redactor that passes events through unchanged."""

    name = "noop"

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def redact(self, event: dict) -> dict:
        return event


class TestSensitivePipeline:
    """AC10: Sensitive container survives build → redact → serialize."""

    @pytest.mark.asyncio
    async def test_sensitive_masked_in_serialized_output(self) -> None:
        """Original sensitive values never appear in the serialized output."""
        original_email = "alice@example.com"
        original_ssn = "123-45-6789"

        envelope = build_envelope(
            level="INFO",
            message="signup",
            extra={
                "sensitive": {"email": original_email, "ssn": original_ssn},
                "action": "register",
            },
        )

        # Redaction pass (noop — sensitive data was already masked at build time)
        redacted = await redact_in_order(
            cast(dict[str, Any], envelope), [_NoopRedactor()]
        )

        # Serialization
        serialized = serialize_envelope(redacted)
        output = (
            serialized.data.decode("utf-8")
            if isinstance(serialized.data, bytes)
            else serialized.data
        )

        # Masked values present
        parsed = json.loads(output)
        assert parsed["log"]["data"]["sensitive"]["email"] == "***"
        assert parsed["log"]["data"]["sensitive"]["ssn"] == "***"

        # Original values absent from entire serialized output
        assert original_email not in output
        assert original_ssn not in output

        # Non-sensitive data unaffected
        assert parsed["log"]["data"]["action"] == "register"

    @pytest.mark.asyncio
    async def test_pii_masked_in_serialized_output(self) -> None:
        """pii= alias values are masked and survive the pipeline."""
        original_token = "sk-secret-abc123"

        envelope = build_envelope(
            level="INFO",
            message="auth",
            extra={"pii": {"api_token": original_token}},
        )

        redacted = await redact_in_order(
            cast(dict[str, Any], envelope), [_NoopRedactor()]
        )
        serialized = serialize_envelope(redacted)
        output = (
            serialized.data.decode("utf-8")
            if isinstance(serialized.data, bytes)
            else serialized.data
        )

        parsed = json.loads(output)
        assert parsed["log"]["data"]["sensitive"]["api_token"] == "***"
        assert original_token not in output
        assert "pii" not in parsed["log"]["data"]
