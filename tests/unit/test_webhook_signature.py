"""Tests for webhook HMAC signature authentication (Story 4.42)."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import httpx
import pytest

from fapilog.plugins.sinks.webhook import (
    SignatureMode,
    WebhookSink,
    WebhookSinkConfig,
)


class _StubPool:
    """Stub HTTP pool for testing."""

    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = outcomes
        self.calls: list[tuple[str, Any, Any]] = []
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    def acquire(self) -> _StubPool:
        return self

    async def __aenter__(self) -> _StubPool:
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any
    ) -> bool:
        return False

    async def post(
        self,
        url: str,
        json: Any = None,
        content: bytes | None = None,
        headers: Any = None,
    ) -> httpx.Response:
        payload = json if json is not None else content
        self.calls.append((url, payload, headers))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.mark.asyncio
async def test_hmac_signature_computed_correctly() -> None:
    """HMAC-SHA256 signature matches expected computation."""
    secret = "test-secret-key"
    payload = {"message": "hello", "level": "info"}

    pool = _StubPool([httpx.Response(200)])
    config = WebhookSinkConfig(
        endpoint="https://hooks.example.com",
        secret=secret,
        signature_mode=SignatureMode.HMAC,
    )
    sink = WebhookSink(config=config, pool=pool)  # type: ignore[arg-type]

    await sink.start()
    await sink.write(payload)
    await sink.stop()

    # Verify the signature header exists and is correct
    _, sent_payload, headers = pool.calls[0]
    signature_header = headers.get("X-Fapilog-Signature-256")

    # Compute expected signature and verify
    body = json.dumps(sent_payload, separators=(",", ":")).encode()
    expected_signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert signature_header == f"sha256={expected_signature}"


@pytest.mark.asyncio
async def test_hmac_signature_in_header() -> None:
    """HMAC mode adds X-Fapilog-Signature-256 header, not X-Webhook-Secret."""
    pool = _StubPool([httpx.Response(200)])
    config = WebhookSinkConfig(
        endpoint="https://hooks.example.com",
        secret="my-secret",
        signature_mode=SignatureMode.HMAC,
    )
    sink = WebhookSink(config=config, pool=pool)  # type: ignore[arg-type]

    await sink.start()
    await sink.write({"test": "data"})
    await sink.stop()

    _, _, headers = pool.calls[0]
    # HMAC mode should have signature header
    assert "X-Fapilog-Signature-256" in headers
    assert headers["X-Fapilog-Signature-256"].startswith("sha256=")
    # HMAC mode should NOT have the legacy secret header
    assert "X-Webhook-Secret" not in headers


@pytest.mark.asyncio
async def test_header_mode_emits_deprecation_warning() -> None:
    """Legacy header mode emits DeprecationWarning when secret is used."""
    pool = _StubPool([httpx.Response(200)])
    config = WebhookSinkConfig(
        endpoint="https://hooks.example.com",
        secret="my-secret",
        # signature_mode defaults to HEADER (legacy)
    )
    sink = WebhookSink(config=config, pool=pool)  # type: ignore[arg-type]

    await sink.start()
    with pytest.warns(
        DeprecationWarning,
        match="X-Webhook-Secret header mode is deprecated",
    ):
        await sink.write({"test": "data"})
    await sink.stop()


@pytest.mark.asyncio
async def test_header_mode_still_works() -> None:
    """Legacy header mode still sends X-Webhook-Secret for backward compatibility."""
    pool = _StubPool([httpx.Response(200)])
    config = WebhookSinkConfig(
        endpoint="https://hooks.example.com",
        secret="my-secret",
        signature_mode=SignatureMode.HEADER,
    )
    sink = WebhookSink(config=config, pool=pool)  # type: ignore[arg-type]

    await sink.start()
    with pytest.warns(DeprecationWarning):
        await sink.write({"test": "data"})
    await sink.stop()

    _, _, headers = pool.calls[0]
    assert headers.get("X-Webhook-Secret") == "my-secret"
    assert "X-Fapilog-Signature-256" not in headers


@pytest.mark.asyncio
async def test_no_secret_no_signature() -> None:
    """When no secret is configured, no authentication headers are added."""
    pool = _StubPool([httpx.Response(200)])
    config = WebhookSinkConfig(
        endpoint="https://hooks.example.com",
        # No secret
    )
    sink = WebhookSink(config=config, pool=pool)  # type: ignore[arg-type]

    await sink.start()
    await sink.write({"test": "data"})
    await sink.stop()

    _, _, headers = pool.calls[0]
    assert "X-Webhook-Secret" not in headers
    assert "X-Fapilog-Signature-256" not in headers


@pytest.mark.asyncio
async def test_hmac_mode_with_batching() -> None:
    """HMAC signature works correctly with batched payloads."""
    secret = "batch-secret"
    pool = _StubPool([httpx.Response(200)])
    config = WebhookSinkConfig(
        endpoint="https://hooks.example.com",
        secret=secret,
        signature_mode=SignatureMode.HMAC,
        batch_size=2,
    )
    sink = WebhookSink(config=config, pool=pool)  # type: ignore[arg-type]

    await sink.start()
    await sink.write({"n": 1})
    await sink.write({"n": 2})
    await sink.stop()

    _, sent_payload, headers = pool.calls[0]
    signature_header = headers.get("X-Fapilog-Signature-256")

    # Verify signature matches the batched payload
    body = json.dumps(sent_payload, separators=(",", ":")).encode()
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert signature_header == f"sha256={expected}"


def test_signature_mode_enum_values() -> None:
    """SignatureMode enum has expected values."""
    assert SignatureMode.HEADER.value == "header"
    assert SignatureMode.HMAC.value == "hmac"


def test_config_accepts_signature_mode_string() -> None:
    """WebhookSinkConfig accepts signature_mode as string."""
    config = WebhookSinkConfig(
        endpoint="https://hooks.example.com",
        secret="test",
        signature_mode="hmac",  # type: ignore[arg-type]
    )
    assert config.signature_mode == SignatureMode.HMAC


def test_config_default_signature_mode_is_header() -> None:
    """Default signature_mode is HEADER for backward compatibility."""
    config = WebhookSinkConfig(
        endpoint="https://hooks.example.com",
        secret="test",
    )
    assert config.signature_mode == SignatureMode.HEADER
