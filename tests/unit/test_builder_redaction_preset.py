"""Unit tests for LoggerBuilder.with_redaction(preset=...) unified API."""

from __future__ import annotations

import pytest


class TestWithRedactionPreset:
    """Tests for builder's with_redaction(preset=...) method."""

    def test_with_redaction_preset_adds_field_mask_redactor(self) -> None:
        """with_redaction(preset=...) enables field_mask redactor."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_redaction(preset="GDPR_PII")

        # Check that field_mask is in redactors list
        redactors = builder._config.get("core", {}).get("redactors", [])
        assert "field_mask" in redactors

    def test_with_redaction_preset_adds_fields_to_mask(self) -> None:
        """with_redaction(preset=...) populates fields_to_mask with preset fields."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_redaction(preset="CONTACT_INFO")

        redactor_config = builder._config.get("redactor_config", {})
        field_mask_config = redactor_config.get("field_mask", {})
        fields_to_mask = field_mask_config.get("fields_to_mask", [])

        # Should include data.email prefix
        assert "data.email" in fields_to_mask
        assert "data.phone" in fields_to_mask

    def test_with_redaction_preset_adds_regex_mask_redactor(self) -> None:
        """with_redaction(preset=...) enables regex_mask redactor when patterns exist."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_redaction(preset="GDPR_PII")

        redactors = builder._config.get("core", {}).get("redactors", [])
        assert "regex_mask" in redactors

    def test_with_redaction_preset_adds_patterns(self) -> None:
        """with_redaction(preset=...) populates regex patterns."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_redaction(preset="CONTACT_INFO")

        redactor_config = builder._config.get("redactor_config", {})
        regex_mask_config = redactor_config.get("regex_mask", {})
        patterns = regex_mask_config.get("patterns", [])

        assert len(patterns) > 0
        assert any("email" in p.lower() for p in patterns)

    def test_with_redaction_preset_unknown_raises_valueerror(self) -> None:
        """with_redaction(preset=...) raises ValueError for unknown preset."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()

        with pytest.raises(ValueError, match="Unknown redaction preset"):
            builder.with_redaction(preset="NONEXISTENT")

    def test_with_redaction_preset_returns_self(self) -> None:
        """with_redaction(preset=...) returns builder for chaining."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        result = builder.with_redaction(preset="GDPR_PII")

        assert result is builder


class TestMultiplePresets:
    """Tests for composing multiple presets."""

    def test_multiple_presets_merge_fields(self) -> None:
        """Multiple presets merge their fields additively."""
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

    def test_multiple_presets_no_duplicate_fields(self) -> None:
        """Multiple presets don't add duplicate fields."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        # Apply same preset twice via list
        builder.with_redaction(preset="CONTACT_INFO")
        builder.with_redaction(preset="CONTACT_INFO")

        redactor_config = builder._config.get("redactor_config", {})
        field_mask_config = redactor_config.get("field_mask", {})
        fields_to_mask = field_mask_config.get("fields_to_mask", [])

        # Count occurrences of data.email
        email_count = fields_to_mask.count("data.email")
        assert email_count == 1


class TestPresetWithCustomFields:
    """Tests for combining presets with custom fields."""

    def test_custom_fields_extend_preset(self) -> None:
        """Custom fields from with_redaction add to preset fields."""
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

    def test_preset_after_custom_fields_merges(self) -> None:
        """Applying preset after custom fields merges both."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_redaction(fields=["custom_field"])
        builder.with_redaction(preset="CONTACT_INFO")

        redactor_config = builder._config.get("redactor_config", {})
        field_mask_config = redactor_config.get("field_mask", {})
        fields_to_mask = field_mask_config.get("fields_to_mask", [])

        # Custom field preserved (with auto-prefix)
        assert "data.custom_field" in fields_to_mask

        # Preset fields added
        assert "data.email" in fields_to_mask


class TestPresetWithMask:
    """Tests for custom mask with presets."""

    def test_preset_with_custom_mask(self) -> None:
        """Preset can use custom mask string."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_redaction(preset="GDPR_PII", mask="[HIDDEN]")

        config = builder._config.get("redactor_config", {}).get("field_mask", {})
        assert config["mask_string"] == "[HIDDEN]"


class TestPresetAutoPrefix:
    """Tests for auto-prefix behavior with presets."""

    def test_preset_fields_get_data_prefix(self) -> None:
        """Preset fields automatically get data. prefix."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_redaction(preset="CONTACT_INFO")

        fields = builder._config["redactor_config"]["field_mask"]["fields_to_mask"]
        # All preset fields should have data. prefix
        for field in fields:
            assert field.startswith("data."), f"Field {field} missing data. prefix"

    def test_custom_fields_auto_prefix(self) -> None:
        """Custom simple fields get auto-prefixed."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_redaction(fields=["password"])

        fields = builder._config["redactor_config"]["field_mask"]["fields_to_mask"]
        assert "data.password" in fields

    def test_custom_fields_no_prefix_when_has_dot(self) -> None:
        """Custom fields with dots are not auto-prefixed."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_redaction(fields=["context.password"])

        fields = builder._config["redactor_config"]["field_mask"]["fields_to_mask"]
        assert "context.password" in fields
        assert "data.context.password" not in fields

    def test_auto_prefix_disabled(self) -> None:
        """auto_prefix=False disables auto-prefixing."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_redaction(fields=["password"], auto_prefix=False)

        fields = builder._config["redactor_config"]["field_mask"]["fields_to_mask"]
        assert "password" in fields
        assert "data.password" not in fields
