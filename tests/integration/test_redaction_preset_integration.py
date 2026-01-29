"""Integration tests for redaction preset end-to-end behavior."""

from __future__ import annotations

import pytest


class TestSinglePresetRedaction:
    """Tests for single preset redaction behavior."""

    @pytest.mark.asyncio
    async def test_single_preset_redacts_fields(self) -> None:
        """Single preset redacts matching fields."""
        from fapilog import LoggerBuilder

        logger = (
            LoggerBuilder()
            .with_redaction(preset="CONTACT_INFO")
            .with_level("INFO")
            .build()
        )

        # Verify the redactor was configured BEFORE drain
        # (drain clears internal lists to allow GC per Story 4.63)
        assert any(r.name == "field_mask" for r in logger._redactors)

        logger.info("user signup", email="john@example.com", phone="555-1234")

        # Drain to ensure all events are processed
        await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_gdpr_preset_redacts_email(self) -> None:
        """GDPR_PII preset redacts email field."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_redaction(preset="GDPR_PII")

        # Verify configuration was set up correctly
        redactor_config = builder._config.get("redactor_config", {})
        field_mask_config = redactor_config.get("field_mask", {})
        fields_to_mask = field_mask_config.get("fields_to_mask", [])

        assert "data.email" in fields_to_mask

    @pytest.mark.asyncio
    async def test_hipaa_preset_redacts_mrn(self) -> None:
        """HIPAA_PHI preset redacts MRN field."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_redaction(preset="HIPAA_PHI")

        redactor_config = builder._config.get("redactor_config", {})
        field_mask_config = redactor_config.get("field_mask", {})
        fields_to_mask = field_mask_config.get("fields_to_mask", [])

        assert "data.mrn" in fields_to_mask
        assert "data.patient_id" in fields_to_mask

    @pytest.mark.asyncio
    async def test_pci_preset_redacts_card_number(self) -> None:
        """PCI_DSS preset redacts card number field."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_redaction(preset="PCI_DSS")

        redactor_config = builder._config.get("redactor_config", {})
        field_mask_config = redactor_config.get("field_mask", {})
        fields_to_mask = field_mask_config.get("fields_to_mask", [])

        assert "data.card_number" in fields_to_mask
        assert "data.cvv" in fields_to_mask


class TestInheritedPresetRedaction:
    """Tests for inherited preset behavior."""

    @pytest.mark.asyncio
    async def test_inherited_preset_redacts_parent_fields(self) -> None:
        """Inherited preset includes parent's fields."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        # GDPR_PII_UK extends GDPR_PII which extends CONTACT_INFO
        builder.with_redaction(preset="GDPR_PII_UK")

        redactor_config = builder._config.get("redactor_config", {})
        field_mask_config = redactor_config.get("field_mask", {})
        fields_to_mask = field_mask_config.get("fields_to_mask", [])

        # From CONTACT_INFO (grandparent via GDPR_PII)
        assert "data.email" in fields_to_mask
        assert "data.phone" in fields_to_mask

        # From UK_GOVERNMENT_IDS (direct parent)
        assert "data.nhs_number" in fields_to_mask

    @pytest.mark.asyncio
    async def test_gdpr_uk_redacts_ni_number(self) -> None:
        """GDPR_PII_UK preset includes UK-specific NI number."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_redaction(preset="GDPR_PII_UK")

        redactor_config = builder._config.get("redactor_config", {})
        field_mask_config = redactor_config.get("field_mask", {})
        fields_to_mask = field_mask_config.get("fields_to_mask", [])

        assert (
            "data.national_insurance" in fields_to_mask
            or "data.ni_number" in fields_to_mask
        )


class TestMultiplePresetsComposable:
    """Tests for composing multiple presets."""

    @pytest.mark.asyncio
    async def test_multiple_presets_composable(self) -> None:
        """Multiple presets can be combined."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_redaction(preset=["GDPR_PII", "PCI_DSS"])

        redactor_config = builder._config.get("redactor_config", {})
        field_mask_config = redactor_config.get("field_mask", {})
        fields_to_mask = field_mask_config.get("fields_to_mask", [])

        # From GDPR_PII
        assert "data.email" in fields_to_mask

        # From PCI_DSS
        assert "data.card_number" in fields_to_mask


class TestCustomFieldsExtendPreset:
    """Tests for extending presets with custom fields."""

    @pytest.mark.asyncio
    async def test_custom_fields_extend_preset(self) -> None:
        """Custom fields add to preset fields."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_redaction(preset="GDPR_PII")
        builder.with_redaction(fields=["patient_id", "mrn"])

        redactor_config = builder._config.get("redactor_config", {})
        field_mask_config = redactor_config.get("field_mask", {})
        fields_to_mask = field_mask_config.get("fields_to_mask", [])

        # From preset
        assert "data.email" in fields_to_mask

        # Custom fields (with auto-prefix)
        assert "data.patient_id" in fields_to_mask
        assert "data.mrn" in fields_to_mask


class TestPresetWithEnvironmentPreset:
    """Tests for using redaction presets with environment presets."""

    @pytest.mark.asyncio
    async def test_preset_with_environment_preset(self) -> None:
        """Redaction preset works with environment preset."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_preset("production")
        builder.with_redaction(preset="HIPAA_PHI")

        # Verify both production redactors and HIPAA fields are present
        redactors = builder._config.get("core", {}).get("redactors", [])
        assert "field_mask" in redactors

        redactor_config = builder._config.get("redactor_config", {})
        field_mask_config = redactor_config.get("field_mask", {})
        fields_to_mask = field_mask_config.get("fields_to_mask", [])

        # HIPAA fields
        assert "data.mrn" in fields_to_mask

        # CREDENTIALS preset should also be applied from production
        assert "data.password" in fields_to_mask

    @pytest.mark.asyncio
    async def test_production_preset_applies_credentials(self) -> None:
        """Production preset automatically applies CREDENTIALS redaction preset."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_preset("production")

        redactor_config = builder._config.get("redactor_config", {})
        field_mask_config = redactor_config.get("field_mask", {})
        fields_to_mask = field_mask_config.get("fields_to_mask", [])

        # From CREDENTIALS preset (automatically applied)
        assert "data.password" in fields_to_mask
        assert "data.api_key" in fields_to_mask
        assert "data.token" in fields_to_mask

    @pytest.mark.asyncio
    async def test_fastapi_preset_applies_credentials(self) -> None:
        """FastAPI preset automatically applies CREDENTIALS redaction preset."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_preset("fastapi")

        redactor_config = builder._config.get("redactor_config", {})
        field_mask_config = redactor_config.get("field_mask", {})
        fields_to_mask = field_mask_config.get("fields_to_mask", [])

        # From CREDENTIALS preset (automatically applied)
        assert "data.password" in fields_to_mask

    @pytest.mark.asyncio
    async def test_serverless_preset_applies_credentials(self) -> None:
        """Serverless preset automatically applies CREDENTIALS redaction preset."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_preset("serverless")

        redactor_config = builder._config.get("redactor_config", {})
        field_mask_config = redactor_config.get("field_mask", {})
        fields_to_mask = field_mask_config.get("fields_to_mask", [])

        # From CREDENTIALS preset (automatically applied)
        assert "data.password" in fields_to_mask
