"""Integration tests for hardened preset.

Story 3.10: Security-Hardened Preset

Tests verify that the hardened preset:
- Applies comprehensive redaction from HIPAA, PCI-DSS, and CREDENTIALS presets (AC6)
- Creates a working logger with all security settings enabled (AC1)
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from fapilog import get_logger, list_presets
from fapilog.core.presets import get_preset
from fapilog.core.settings import Settings

pytestmark = [pytest.mark.integration, pytest.mark.security]


async def _collecting_sink(
    collected: list[dict[str, Any]], entry: dict[str, Any]
) -> None:
    """Helper sink that collects events for inspection."""
    collected.append(dict(entry))


class TestHardenedPresetDiscovery:
    """Test that hardened preset is discoverable."""

    def test_hardened_preset_in_list(self):
        """AC1: Hardened preset is discoverable via list_presets."""
        presets = list_presets()
        assert "hardened" in presets

    def test_hardened_preset_returns_config(self):
        """AC1: get_preset returns valid config for hardened."""
        config = get_preset("hardened")
        assert "core" in config
        assert config["core"]["redaction_fail_mode"] == "closed"


class TestHardenedPresetRedactionFields:
    """Test comprehensive redaction preset application (AC6)."""

    def test_hardened_preset_applies_hipaa_fields(self):
        """AC6: Hardened preset applies HIPAA_PHI redaction fields."""
        config = get_preset("hardened")
        # Verify Settings creation works (fields applied at logger creation)
        Settings(**config)

        # HIPAA fields (via resolve in get_logger)
        # These are applied at logger creation time, so we verify
        # the preset has the marker for application
        redaction_presets = config.get("_apply_redaction_presets", [])
        assert "HIPAA_PHI" in redaction_presets

    def test_hardened_preset_applies_pci_dss_fields(self):
        """AC6: Hardened preset applies PCI_DSS redaction fields."""
        config = get_preset("hardened")

        redaction_presets = config.get("_apply_redaction_presets", [])
        assert "PCI_DSS" in redaction_presets

    def test_hardened_preset_applies_credentials_fields(self):
        """AC6: Hardened preset applies CREDENTIALS redaction fields."""
        config = get_preset("hardened")

        # Legacy marker for CREDENTIALS
        assert config.get("_apply_credentials_preset") is True


@pytest.mark.asyncio
async def test_hardened_preset_creates_working_logger():
    """AC1: Logger can be created with hardened preset and logs work."""
    collected: list[dict[str, Any]] = []

    logger = get_logger(name="test-hardened", preset="hardened")

    async def sink(entry: dict[str, Any]) -> None:
        await _collecting_sink(collected, entry)

    logger._sink_write = sink  # type: ignore[attr-defined]

    # Log a test message
    logger.info("test message", user_id="12345")
    await asyncio.sleep(0)
    await logger.stop_and_drain()

    assert collected, "Expected at least one emitted entry"
    event = collected[0]
    assert event["message"] == "test message"


@pytest.mark.asyncio
async def test_hardened_preset_redacts_credentials():
    """Hardened preset redacts credential fields."""
    collected: list[dict[str, Any]] = []

    logger = get_logger(name="test-hardened-creds", preset="hardened")

    async def sink(entry: dict[str, Any]) -> None:
        await _collecting_sink(collected, entry)

    logger._sink_write = sink  # type: ignore[attr-defined]

    # Log with sensitive credential data
    logger.info(
        "auth attempt",
        password="secret123",
        api_key="sk-1234567890",
    )
    await asyncio.sleep(0)
    await logger.stop_and_drain()

    assert collected, "Expected at least one emitted entry"
    event = collected[0]
    data = event.get("data", {})

    # Credentials should be redacted
    password = data.get("password", "")
    api_key = data.get("api_key", "")

    assert "secret123" not in password, f"Password should be redacted, got: {password}"
    assert "sk-1234567890" not in api_key, f"API key should be redacted, got: {api_key}"


@pytest.mark.asyncio
async def test_hardened_preset_redacts_pci_fields():
    """Hardened preset redacts PCI-DSS fields."""
    collected: list[dict[str, Any]] = []

    logger = get_logger(name="test-hardened-pci", preset="hardened")

    async def sink(entry: dict[str, Any]) -> None:
        await _collecting_sink(collected, entry)

    logger._sink_write = sink  # type: ignore[attr-defined]

    # Log with PCI-DSS sensitive data
    logger.info(
        "payment",
        card_number="4111111111111111",
        cvv="123",
    )
    await asyncio.sleep(0)
    await logger.stop_and_drain()

    assert collected, "Expected at least one emitted entry"
    event = collected[0]
    data = event.get("data", {})

    # PCI fields should be redacted
    card = data.get("card_number", "")
    cvv = data.get("cvv", "")

    assert "4111111111111111" not in card, (
        f"Card number should be redacted, got: {card}"
    )
    assert "123" not in cvv, f"CVV should be redacted, got: {cvv}"


@pytest.mark.asyncio
async def test_hardened_preset_redacts_hipaa_fields():
    """Hardened preset redacts HIPAA PHI fields."""
    collected: list[dict[str, Any]] = []

    logger = get_logger(name="test-hardened-hipaa", preset="hardened")

    async def sink(entry: dict[str, Any]) -> None:
        await _collecting_sink(collected, entry)

    logger._sink_write = sink  # type: ignore[attr-defined]

    # Log with HIPAA PHI data
    logger.info(
        "patient record",
        ssn="123-45-6789",
        mrn="MRN-001234",
    )
    await asyncio.sleep(0)
    await logger.stop_and_drain()

    assert collected, "Expected at least one emitted entry"
    event = collected[0]
    data = event.get("data", {})

    # HIPAA fields should be redacted
    ssn = data.get("ssn", "")
    mrn = data.get("mrn", "")

    assert "123-45-6789" not in ssn, f"SSN should be redacted, got: {ssn}"
    assert "MRN-001234" not in mrn, f"MRN should be redacted, got: {mrn}"
