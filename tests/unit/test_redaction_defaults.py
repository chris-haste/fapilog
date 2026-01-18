"""Snapshot tests validating redaction defaults match documentation.

These tests prevent drift between docs, presets, and settings by asserting
the exact redaction configuration. Update both code AND docs if these fail.

Story: 4.47 - Redaction Defaults Alignment
"""

from __future__ import annotations

import pytest

from fapilog import Settings
from fapilog.core.presets import PRESETS, get_preset


class TestDefaultSettingsRedactors:
    """Verify Settings() defaults match documentation claims."""

    def test_default_redactors_empty(self) -> None:
        """Default Settings has no redactors enabled.

        Docs claim: 'With no preset, redaction is disabled by default.'
        """
        settings = Settings()
        assert settings.core.redactors == []

    def test_enable_redactors_true_by_default(self) -> None:
        """Redactors stage is enabled by default (just no redactors configured).

        Docs claim: 'Redactors enabled: core.enable_redactors=True'
        """
        settings = Settings()
        assert settings.core.enable_redactors is True

    def test_redactors_order_includes_all_builtin(self) -> None:
        """Default redactors_order includes field-mask, regex-mask, url-credentials.

        This defines processing order when redactors are active.
        """
        settings = Settings()
        assert "field-mask" in settings.core.redactors_order
        assert "regex-mask" in settings.core.redactors_order
        assert "url-credentials" in settings.core.redactors_order


class TestProductionPresetRedactors:
    """Verify production preset matches documentation claims."""

    def test_production_includes_field_mask(self) -> None:
        """Production preset enables field_mask redactor."""
        prod = get_preset("production")
        assert "field_mask" in prod["core"]["redactors"]

    def test_production_includes_regex_mask(self) -> None:
        """Production preset enables regex_mask redactor.

        Docs claim regex-based secret matching is active in production.
        """
        prod = get_preset("production")
        assert "regex_mask" in prod["core"]["redactors"]

    def test_production_includes_url_credentials(self) -> None:
        """Production preset enables url_credentials redactor."""
        prod = get_preset("production")
        assert "url_credentials" in prod["core"]["redactors"]

    def test_production_redactor_order(self) -> None:
        """Production redactors are in documented order: field_mask, regex_mask, url_credentials."""
        prod = get_preset("production")
        expected_order = ["field_mask", "regex_mask", "url_credentials"]
        assert prod["core"]["redactors"] == expected_order


class TestProductionFieldMaskConfig:
    """Verify field_mask configuration matches documentation."""

    def test_field_mask_fields_match_docs(self) -> None:
        """Production field_mask masks documented sensitive fields.

        These fields are documented in redaction-guarantee.md and should
        mask at any nesting level under metadata.*.
        """
        prod = get_preset("production")
        fields = prod["redactor_config"]["field_mask"]["fields_to_mask"]

        # Documented fields that must be masked
        required_fields = [
            "metadata.password",
            "metadata.api_key",
            "metadata.token",
            "metadata.secret",
            "metadata.authorization",
            "metadata.api_secret",
            "metadata.private_key",
            "metadata.ssn",
            "metadata.credit_card",
        ]

        for field in required_fields:
            assert field in fields, f"Missing required field: {field}"


class TestProductionRegexMaskConfig:
    """Verify regex_mask configuration matches documentation."""

    def test_regex_mask_has_patterns(self) -> None:
        """Production regex_mask has patterns configured."""
        prod = get_preset("production")
        patterns = prod["redactor_config"]["regex_mask"]["patterns"]
        assert len(patterns) > 0, "regex_mask must have patterns configured"

    def test_regex_mask_patterns_cover_sensitive_fields(self) -> None:
        """Regex patterns cover documented sensitive field names.

        Patterns should match paths containing: password, api_key, token,
        secret, authorization, private_key, ssn, credit_card.
        """
        prod = get_preset("production")
        patterns = prod["redactor_config"]["regex_mask"]["patterns"]
        patterns_joined = " ".join(patterns).lower()

        # These keywords must appear in at least one pattern
        required_keywords = [
            "password",
            "api",  # Covers api_key, apikey
            "token",
            "secret",
            "authorization",
            "ssn",
        ]

        for keyword in required_keywords:
            assert keyword in patterns_joined, (
                f"No pattern covers '{keyword}' - regex_mask must catch "
                f"fields containing this keyword"
            )


class TestOtherPresetsNoRedactors:
    """Verify non-production presets have no redactors (as documented)."""

    @pytest.mark.parametrize(
        "preset_name",
        ["dev", "fastapi", "minimal"],
    )
    def test_preset_has_no_redactors(self, preset_name: str) -> None:
        """Non-production presets do not enable redactors by default.

        Docs claim: dev, fastapi, minimal have no redaction protection.
        """
        preset = get_preset(preset_name)

        # Preset may not have core.redactors key, or it may be empty
        redactors = preset.get("core", {}).get("redactors", [])
        assert redactors == [], f"{preset_name} preset should have no redactors"


class TestPresetConsistency:
    """Ensure all presets are accounted for in documentation."""

    def test_all_presets_documented(self) -> None:
        """All defined presets should be documented in redaction-guarantee.md.

        This test ensures new presets get documented.
        """
        expected_presets = {"dev", "production", "fastapi", "minimal"}
        actual_presets = set(PRESETS.keys())

        assert actual_presets == expected_presets, (
            f"Preset mismatch - update docs if presets changed. "
            f"Expected: {expected_presets}, Got: {actual_presets}"
        )
