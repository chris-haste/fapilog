"""Unit tests for redaction preset definitions and inheritance."""

from __future__ import annotations

import pytest


class TestRedactionPresetDataclass:
    """Tests for RedactionPreset dataclass structure and immutability."""

    def test_preset_has_required_attributes(self) -> None:
        """RedactionPreset exposes name, description, fields, patterns, extends."""
        from fapilog.redaction import RedactionPreset

        preset = RedactionPreset(
            name="TEST",
            description="Test preset",
            fields=("email", "phone"),
            patterns=(r"(?i).*email.*",),
            extends=(),
            regulation="GDPR",
            region="EU",
            tags=("pii", "test"),
        )

        assert preset.name == "TEST"
        assert preset.description == "Test preset"
        assert preset.fields == ("email", "phone")
        assert preset.patterns == (r"(?i).*email.*",)
        assert preset.extends == ()
        assert preset.regulation == "GDPR"
        assert preset.region == "EU"
        assert preset.tags == ("pii", "test")

    def test_preset_is_immutable(self) -> None:
        """RedactionPreset is frozen (immutable)."""
        from fapilog.redaction import RedactionPreset

        preset = RedactionPreset(
            name="TEST",
            description="Test preset",
        )

        with pytest.raises((AttributeError, TypeError)):
            preset.name = "CHANGED"  # type: ignore[misc]

    def test_preset_defaults(self) -> None:
        """RedactionPreset has sensible defaults for optional fields."""
        from fapilog.redaction import RedactionPreset

        preset = RedactionPreset(
            name="TEST",
            description="Test preset",
        )

        assert preset.fields == ()
        assert preset.patterns == ()
        assert preset.extends == ()
        assert preset.regulation is None
        assert preset.region is None
        assert preset.tags == ()


class TestPresetRegistry:
    """Tests for preset registry functions."""

    def test_list_presets_returns_all_builtin_names(self) -> None:
        """list_redaction_presets returns all expected builtin preset names."""
        from fapilog.redaction import list_redaction_presets

        presets = list_redaction_presets()

        # Base presets
        assert "CONTACT_INFO" in presets
        assert "PERSONAL_IDENTIFIERS" in presets
        assert "ONLINE_IDENTIFIERS" in presets
        assert "FINANCIAL_IDENTIFIERS" in presets

        # Regional presets
        assert "US_GOVERNMENT_IDS" in presets
        assert "UK_GOVERNMENT_IDS" in presets
        assert "EU_GOVERNMENT_IDS" in presets

        # Regulation presets
        assert "GDPR_PII" in presets
        assert "GDPR_PII_UK" in presets
        assert "CCPA_PII" in presets
        assert "HIPAA_PHI" in presets
        assert "PCI_DSS" in presets
        assert "CREDENTIALS" in presets

    def test_get_preset_returns_preset_object(self) -> None:
        """get_redaction_preset returns correct preset object."""
        from fapilog.redaction import RedactionPreset, get_redaction_preset

        gdpr = get_redaction_preset("GDPR_PII")

        assert isinstance(gdpr, RedactionPreset)
        assert gdpr.name == "GDPR_PII"
        assert gdpr.description == "GDPR Article 4 personal data identifiers"
        assert gdpr.regulation == "GDPR"
        assert gdpr.region == "EU"

    def test_get_preset_unknown_raises_valueerror(self) -> None:
        """get_redaction_preset raises ValueError for unknown preset."""
        from fapilog.redaction import get_redaction_preset

        with pytest.raises(ValueError, match="Unknown redaction preset"):
            get_redaction_preset("NONEXISTENT_PRESET")

    def test_preset_metadata_fields(self) -> None:
        """Presets have proper metadata fields populated."""
        from fapilog.redaction import get_redaction_preset

        hipaa = get_redaction_preset("HIPAA_PHI")
        assert hipaa.regulation == "HIPAA"
        assert hipaa.region == "US"
        assert "healthcare" in hipaa.tags
        assert "hipaa" in hipaa.tags


class TestPresetInheritance:
    """Tests for preset inheritance resolution."""

    def test_resolve_preset_includes_own_fields(self) -> None:
        """resolve_preset_fields includes the preset's own fields."""
        from fapilog.redaction import resolve_preset_fields

        fields, patterns = resolve_preset_fields("CONTACT_INFO")

        assert "email" in fields
        assert "phone" in fields
        assert "address" in fields

    def test_resolve_preset_includes_parent_fields(self) -> None:
        """resolve_preset_fields includes inherited parent fields."""
        from fapilog.redaction import resolve_preset_fields

        fields, patterns = resolve_preset_fields("GDPR_PII")

        # From CONTACT_INFO parent
        assert "email" in fields
        assert "phone" in fields

        # From PERSONAL_IDENTIFIERS parent
        assert "name" in fields
        assert "dob" in fields

        # Own fields
        assert "biometric_data" in fields

    def test_resolve_preset_includes_grandparent_fields(self) -> None:
        """resolve_preset_fields includes multi-level inherited fields."""
        from fapilog.redaction import resolve_preset_fields

        # GDPR_PII_UK extends GDPR_PII, which extends CONTACT_INFO
        fields, patterns = resolve_preset_fields("GDPR_PII_UK")

        # From CONTACT_INFO (grandparent via GDPR_PII)
        assert "email" in fields
        assert "phone" in fields

        # From UK_GOVERNMENT_IDS (direct parent)
        assert "nhs_number" in fields
        assert "national_insurance" in fields or "ni_number" in fields

    def test_circular_inheritance_raises_error(self) -> None:
        """Circular inheritance is detected and raises ValueError."""
        from fapilog.redaction import RedactionPreset

        # Create presets with circular inheritance
        preset_a = RedactionPreset(
            name="PRESET_A",
            description="Test A",
            extends=("PRESET_B",),
        )
        preset_b = RedactionPreset(
            name="PRESET_B",
            description="Test B",
            extends=("PRESET_A",),
        )

        registry = {"PRESET_A": preset_a, "PRESET_B": preset_b}

        with pytest.raises(ValueError, match="Circular inheritance detected"):
            preset_a.resolve(registry)


class TestPresetFiltering:
    """Tests for preset filtering functions."""

    def test_get_presets_by_regulation(self) -> None:
        """get_presets_by_regulation returns matching presets."""
        from fapilog.redaction import get_presets_by_regulation

        gdpr_presets = get_presets_by_regulation("GDPR")
        assert "GDPR_PII" in gdpr_presets

        hipaa_presets = get_presets_by_regulation("HIPAA")
        assert "HIPAA_PHI" in hipaa_presets

    def test_get_presets_by_region(self) -> None:
        """get_presets_by_region returns matching presets."""
        from fapilog.redaction import get_presets_by_region

        us_presets = get_presets_by_region("US")
        assert "HIPAA_PHI" in us_presets
        assert "US_GOVERNMENT_IDS" in us_presets

        uk_presets = get_presets_by_region("UK")
        assert "GDPR_PII_UK" in uk_presets
        assert "UK_GOVERNMENT_IDS" in uk_presets

    def test_get_presets_by_tag(self) -> None:
        """get_presets_by_tag returns matching presets."""
        from fapilog.redaction import get_presets_by_tag

        pii_presets = get_presets_by_tag("pii")
        assert "GDPR_PII" in pii_presets
        assert "CCPA_PII" in pii_presets

        healthcare_presets = get_presets_by_tag("healthcare")
        assert "HIPAA_PHI" in healthcare_presets


class TestPresetFieldCoverage:
    """Tests verifying presets cover required fields for compliance."""

    def test_gdpr_preset_resolves_contact_fields(self) -> None:
        """GDPR_PII preset includes contact information fields."""
        from fapilog.redaction import resolve_preset_fields

        fields, patterns = resolve_preset_fields("GDPR_PII")

        assert "email" in fields
        assert "phone" in fields
        assert "address" in fields

    def test_gdpr_preset_resolves_identity_fields(self) -> None:
        """GDPR_PII preset includes personal identity fields."""
        from fapilog.redaction import resolve_preset_fields

        fields, patterns = resolve_preset_fields("GDPR_PII")

        assert "name" in fields or "first_name" in fields
        assert "dob" in fields or "date_of_birth" in fields

    def test_gdpr_preset_resolves_government_ids(self) -> None:
        """GDPR_PII preset includes EU government ID fields."""
        from fapilog.redaction import resolve_preset_fields

        fields, patterns = resolve_preset_fields("GDPR_PII")

        assert "passport" in fields
        assert "national_id" in fields

    def test_gdpr_preset_resolves_online_identifiers(self) -> None:
        """GDPR_PII preset includes online identifier fields."""
        from fapilog.redaction import resolve_preset_fields

        fields, patterns = resolve_preset_fields("GDPR_PII")

        assert "ip" in fields or "ip_address" in fields
        assert "device_id" in fields

    def test_gdpr_preset_resolves_financial_identifiers(self) -> None:
        """GDPR_PII preset includes financial identifier fields."""
        from fapilog.redaction import resolve_preset_fields

        fields, patterns = resolve_preset_fields("GDPR_PII")

        assert "iban" in fields
        assert "account_number" in fields or "bank_account" in fields

    def test_gdpr_uk_includes_nhs_number(self) -> None:
        """GDPR_PII_UK preset includes UK-specific NHS number."""
        from fapilog.redaction import resolve_preset_fields

        fields, _ = resolve_preset_fields("GDPR_PII_UK")

        assert "nhs_number" in fields

    def test_ccpa_includes_ssn(self) -> None:
        """CCPA_PII preset includes SSN field."""
        from fapilog.redaction import resolve_preset_fields

        fields, _ = resolve_preset_fields("CCPA_PII")

        assert "ssn" in fields or "social_security" in fields

    def test_hipaa_includes_mrn(self) -> None:
        """HIPAA_PHI preset includes medical record number."""
        from fapilog.redaction import resolve_preset_fields

        fields, _ = resolve_preset_fields("HIPAA_PHI")

        assert "mrn" in fields or "medical_record_number" in fields
        assert "patient_id" in fields

    def test_pci_includes_card_fields(self) -> None:
        """PCI_DSS preset includes card-related fields."""
        from fapilog.redaction import resolve_preset_fields

        fields, _ = resolve_preset_fields("PCI_DSS")

        assert "card_number" in fields or "credit_card" in fields
        assert "cvv" in fields or "cvc" in fields
        assert "expiry" in fields or "expiry_date" in fields

    def test_credentials_includes_secrets(self) -> None:
        """CREDENTIALS preset includes authentication secrets."""
        from fapilog.redaction import resolve_preset_fields

        fields, _ = resolve_preset_fields("CREDENTIALS")

        assert "password" in fields
        assert "api_key" in fields
        assert "token" in fields or "access_token" in fields
