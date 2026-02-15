"""Integration tests for secure defaults - URL credential redaction.

Story 3.7: Secure Defaults - URL Credential Redaction

These tests verify end-to-end that:
- URL credentials are scrubbed by default (AC1)
- Opt-out mechanism preserves URLs (AC2)
- Preset redaction behavior works correctly (AC3)
"""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlparse

import pytest

from fapilog import Settings, get_logger

pytestmark = [pytest.mark.integration, pytest.mark.security]


class _CollectingSink:
    """Sink object that collects events for inspection."""

    def __init__(self) -> None:
        self.collected: list[dict[str, Any]] = []

    async def write(self, entry: dict[str, Any]) -> None:
        self.collected.append(dict(entry))

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass


@pytest.mark.asyncio
async def test_url_credentials_scrubbed_by_default() -> None:
    """AC1: URL credentials are scrubbed by default with no preset/config.

    With no preset or explicit redactor config, URLs containing credentials
    should have those credentials removed from the output.
    """
    # Default settings - no preset, no explicit config
    settings = Settings()
    assert settings.core.redactors == ["url_credentials"], (
        "Default should enable url_credentials"
    )

    # Provide sink at construction time via sinks parameter
    collecting = _CollectingSink()
    logger = get_logger(name="test-secure-default", sinks=[collecting], reuse=False)

    # Log with URL containing credentials
    logger.info("connecting", url="https://alice:secret@api.example.com/auth")
    await asyncio.sleep(0)
    await logger.stop_and_drain()

    assert collecting.collected, "Expected at least one emitted entry"
    event = collecting.collected[0]

    # Check that credentials were scrubbed from data
    data = event.get("data", {})
    url = data.get("url", "")

    # Credentials should be removed
    assert "alice" not in url, f"Username should be scrubbed, got: {url}"
    assert "secret" not in url, f"Password should be scrubbed, got: {url}"
    # Host should remain (use urlparse for proper structural check)
    parsed = urlparse(url)
    assert parsed.hostname == "api.example.com", f"Host should remain, got: {url}"


@pytest.mark.asyncio
async def test_opt_out_preserves_urls() -> None:
    """AC2: Explicit empty redactors preserves URLs with credentials.

    Users can opt-out by setting redactors=[], which should preserve
    URLs exactly as provided.
    """
    # Explicitly opt-out of redaction
    settings = Settings(core={"redactors": []})
    assert settings.core.redactors == [], "Explicit opt-out should work"

    # Provide sink at construction time via sinks parameter
    collecting = _CollectingSink()
    logger = get_logger(
        name="test-opt-out", settings=settings, sinks=[collecting], reuse=False
    )

    # Log with URL containing credentials
    test_url = "https://user:pass@example.com/path"
    logger.info("debug", url=test_url)
    await asyncio.sleep(0)
    await logger.stop_and_drain()

    assert collecting.collected, "Expected at least one emitted entry"
    event = collecting.collected[0]

    # Check that URL is preserved exactly
    data = event.get("data", {})
    url = data.get("url", "")

    assert url == test_url, f"URL should be preserved exactly, got: {url}"


@pytest.mark.asyncio
async def test_production_preset_has_full_redaction() -> None:
    """AC3: Production preset has all redactors enabled."""
    # Provide sink at construction time via sinks parameter
    collecting = _CollectingSink()
    logger = get_logger(
        name="test-production", preset="production", sinks=[collecting], reuse=False
    )

    # Log with URL containing credentials
    logger.info("login", url="https://admin:password123@db.example.com/connect")
    await asyncio.sleep(0)
    await logger.stop_and_drain()

    assert collecting.collected, "Expected at least one emitted entry"
    event = collecting.collected[0]

    data = event.get("data", {})
    url = data.get("url", "")

    # Production preset should scrub credentials
    assert "admin" not in url, f"Username should be scrubbed, got: {url}"
    assert "password123" not in url, f"Password should be scrubbed, got: {url}"


@pytest.mark.asyncio
async def test_dev_preset_opts_out() -> None:
    """AC3: Dev preset explicitly opts out of redaction."""
    # Provide sink at construction time via sinks parameter
    collecting = _CollectingSink()
    logger = get_logger(name="test-dev", preset="dev", sinks=[collecting], reuse=False)

    # Log with URL containing credentials
    test_url = "https://dev:devpass@localhost/api"
    logger.info("debug", url=test_url)
    await asyncio.sleep(0)
    await logger.stop_and_drain()

    assert collecting.collected, "Expected at least one emitted entry"
    event = collecting.collected[0]

    data = event.get("data", {})
    url = data.get("url", "")

    # Dev preset should preserve URLs for debugging
    assert url == test_url, f"Dev preset should preserve URL, got: {url}"
