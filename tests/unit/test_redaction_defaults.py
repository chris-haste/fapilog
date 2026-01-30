"""Snapshot tests validating redaction defaults match documentation.

These tests prevent drift between docs, presets, and settings by asserting
the exact redaction configuration. Update both code AND docs if these fail.

Story: 4.47 - Redaction Defaults Alignment
Story: 3.7 - Secure Defaults - URL Credential Redaction
"""

from __future__ import annotations

import pytest

from fapilog import Settings
from fapilog.core.presets import PRESETS, get_preset


class TestDefaultSettingsRedactors:
    """Verify Settings() defaults match documentation claims."""

    def test_default_redactors_includes_url_credentials(self) -> None:
        """Default Settings enables url_credentials redactor for secure defaults.

        Story 3.7: URL credential redaction is enabled by default.
        """
        settings = Settings()
        assert settings.core.redactors == ["url_credentials"]

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


class TestExplicitOptOut:
    """Verify users can explicitly disable redaction."""

    def test_explicit_empty_redactors_disables_all(self) -> None:
        """Setting redactors=[] explicitly disables all redaction.

        Story 3.7 AC2: Users can explicitly disable URL credential redaction.
        """
        settings = Settings(core={"redactors": []})
        assert settings.core.redactors == []


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
    """Verify field_mask configuration via builder with CREDENTIALS preset."""

    def test_field_mask_fields_match_docs_via_builder(self) -> None:
        """Production preset via builder masks documented sensitive fields.

        These fields are documented in redaction-guarantee.md. Since production
        preset now uses CREDENTIALS redaction preset via with_preset(), we test
        through the builder to get the full resolved configuration.
        """
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_preset("production")

        fields = builder._config["redactor_config"]["field_mask"]["fields_to_mask"]

        # Documented fields that must be masked (using v1.1 schema "data" prefix)
        required_fields = [
            "data.password",
            "data.api_key",
            "data.token",
            "data.secret",
            "data.authorization",
            "data.api_secret",
            "data.private_key",
        ]

        for field in required_fields:
            assert field in fields, f"Missing required field: {field}"


class TestProductionRegexMaskConfig:
    """Verify regex_mask configuration via builder with CREDENTIALS preset."""

    def test_regex_mask_has_patterns_via_builder(self) -> None:
        """Production preset via builder has patterns configured."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_preset("production")

        patterns = builder._config["redactor_config"]["regex_mask"]["patterns"]
        assert len(patterns) > 0, "regex_mask must have patterns configured"

    def test_regex_mask_patterns_cover_sensitive_fields_via_builder(self) -> None:
        """Regex patterns cover documented sensitive field names.

        Patterns should match paths containing: password, api_key, token,
        secret, authorization, private_key.
        """
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_preset("production")

        patterns = builder._config["redactor_config"]["regex_mask"]["patterns"]
        patterns_joined = " ".join(patterns).lower()

        # These keywords must appear in at least one pattern
        required_keywords = [
            "password",
            "api",  # Covers api_key, apikey
            "token",
            "secret",
            "auth",  # Covers authorization
        ]

        for keyword in required_keywords:
            assert keyword in patterns_joined, (
                f"No pattern covers '{keyword}' - regex_mask must catch "
                f"fields containing this keyword"
            )


class TestFastapiPresetRedactors:
    """Verify fastapi preset enables redaction.

    Story 10.21: FastAPI preset should enable redaction by default.
    """

    def test_fastapi_preset_enables_redactors(self) -> None:
        """FastAPI preset enables redactors for security by default.

        Story 10.21 AC1: FastAPI preset enables same redactors as production.
        """
        fastapi = get_preset("fastapi")
        production = get_preset("production")
        assert fastapi["core"]["redactors"] == production["core"]["redactors"]

    def test_fastapi_preset_redactor_config_matches_production(self) -> None:
        """FastAPI preset redactor_config matches production preset.

        Story 10.21 AC1: Redactor config should match production.
        """
        fastapi = get_preset("fastapi")
        production = get_preset("production")
        assert fastapi["redactor_config"] == production["redactor_config"]


class TestDevAndMinimalPresetsExplicitOptOut:
    """Verify dev and minimal presets explicitly opt-out of redaction.

    Story 3.7 AC3: Presets continue to work as documented.
    """

    @pytest.mark.parametrize(
        "preset_name",
        ["dev", "minimal"],
    )
    def test_preset_explicitly_opts_out(self, preset_name: str) -> None:
        """Dev and minimal presets explicitly set redactors=[] to opt-out.

        Story 3.7: Presets must explicitly disable redaction (not rely on defaults).
        """
        preset = get_preset(preset_name)

        # Preset MUST explicitly set redactors: [] to opt-out
        assert "core" in preset, f"{preset_name} preset must have core section"
        assert "redactors" in preset["core"], (
            f"{preset_name} preset must explicitly set redactors to opt-out"
        )
        assert preset["core"]["redactors"] == [], (
            f"{preset_name} preset should explicitly set redactors=[] to opt-out"
        )


class TestPresetConsistency:
    """Ensure all presets are accounted for in documentation."""

    def test_all_presets_documented(self) -> None:
        """All defined presets should be documented in redaction-guarantee.md.

        This test ensures new presets get documented.
        """
        expected_presets = {
            "dev",
            "production",
            "production-latency",
            "fastapi",
            "minimal",
            "serverless",
            "hardened",
        }
        actual_presets = set(PRESETS.keys())

        assert actual_presets == expected_presets, (
            f"Preset mismatch - update docs if presets changed. "
            f"Expected: {expected_presets}, Got: {actual_presets}"
        )


class TestFailClosedDefaults:
    """Verify fail-closed defaults for redaction security.

    Story 4.61: Redaction should fail-closed by default to prevent PII leaks.
    """

    def test_on_guardrail_exceeded_default_is_replace_subtree(self) -> None:
        """AC1: FieldMaskConfig.on_guardrail_exceeded defaults to replace_subtree.

        When guardrails are exceeded, unscanned data should be masked (not passed through).
        """
        from fapilog.plugins.redactors.field_mask import FieldMaskConfig

        config = FieldMaskConfig(fields_to_mask=["password"])
        assert config.on_guardrail_exceeded == "replace_subtree"

    def test_block_on_unredactable_default_is_true(self) -> None:
        """AC2: FieldMaskConfig.block_on_unredactable defaults to True.

        If a configured field can't be redacted, the event should be dropped.
        """
        from fapilog.plugins.redactors.field_mask import FieldMaskConfig

        config = FieldMaskConfig(fields_to_mask=["password"])
        assert config.block_on_unredactable is True

    def test_redaction_fail_mode_default_is_warn(self) -> None:
        """AC3: CoreSettings.redaction_fail_mode defaults to warn.

        On redaction exceptions, emit diagnostic (don't silently pass through).
        """
        settings = Settings()
        assert settings.core.redaction_fail_mode == "warn"

    def test_plugin_metadata_defaults_are_fail_closed(self) -> None:
        """PLUGIN_METADATA default_config should match fail-closed defaults."""
        from typing import Any, cast

        from fapilog.plugins.redactors.field_mask import PLUGIN_METADATA

        defaults = cast(dict[str, Any], PLUGIN_METADATA["default_config"])
        assert defaults["on_guardrail_exceeded"] == "replace_subtree"
        assert defaults["block_on_unredactable"] is True
