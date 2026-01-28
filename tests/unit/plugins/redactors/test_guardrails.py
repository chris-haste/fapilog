"""Tests for core redaction guardrails overriding per-redactor settings.

Story 4.57: Make Core Redaction Guardrails Functional

The core guardrails (redaction_max_depth, redaction_max_keys_scanned) in CoreSettings
should act as outer limits that override per-redactor settings when more restrictive.
"""

from __future__ import annotations

import pytest

from fapilog.plugins.redactors.field_mask import FieldMaskConfig, FieldMaskRedactor
from fapilog.plugins.redactors.regex_mask import RegexMaskConfig, RegexMaskRedactor

pytestmark = pytest.mark.security


class TestFieldMaskGuardrails:
    """Tests for FieldMaskRedactor core guardrail behavior."""

    @pytest.mark.asyncio
    async def test_core_max_depth_overrides_plugin_when_more_restrictive(self) -> None:
        """Core max_depth=3 should override plugin default of 16."""
        # Plugin default is max_depth=16, but core says max_depth=3
        # Use on_guardrail_exceeded="warn" to test guardrail limits (not masking behavior)
        redactor = FieldMaskRedactor(
            config=FieldMaskConfig(
                fields_to_mask=["level1.level2.level3.level4.secret"],
                max_depth=16,  # Plugin setting
                on_guardrail_exceeded="warn",  # Test limit behavior, not masking
            ),
            core_max_depth=3,  # Core override - more restrictive
        )

        # depth 0: root, depth 1: level1, depth 2: level2, depth 3: level3
        # depth 4: level4 - exceeds max_depth=3, should NOT be redacted
        event = {
            "level1": {"level2": {"level3": {"level4": {"secret": "sensitive_data"}}}}
        }

        result = await redactor.redact(event)

        # Secret at depth 4 should NOT be redacted because core limit of 3 is exceeded
        assert (
            result["level1"]["level2"]["level3"]["level4"]["secret"] == "sensitive_data"
        )

    @pytest.mark.asyncio
    async def test_plugin_max_depth_applies_when_more_restrictive_than_core(
        self,
    ) -> None:
        """Plugin max_depth=2 should apply when core allows max_depth=20."""
        redactor = FieldMaskRedactor(
            config=FieldMaskConfig(
                fields_to_mask=["level1.level2.level3.secret"],
                max_depth=2,  # Plugin setting - more restrictive
                on_guardrail_exceeded="warn",  # Test limit behavior, not masking
            ),
            core_max_depth=20,  # Core allows more depth
        )

        event = {"level1": {"level2": {"level3": {"secret": "sensitive_data"}}}}

        result = await redactor.redact(event)

        # Secret at depth 3 should NOT be redacted because plugin limit of 2 is exceeded
        assert result["level1"]["level2"]["level3"]["secret"] == "sensitive_data"

    @pytest.mark.asyncio
    async def test_core_max_keys_overrides_plugin_when_more_restrictive(self) -> None:
        """Core max_keys_scanned=5 should override plugin default of 1000."""
        redactor = FieldMaskRedactor(
            config=FieldMaskConfig(
                fields_to_mask=["data.*.secret"],
                max_keys_scanned=1000,  # Plugin setting
                on_guardrail_exceeded="warn",  # Test limit behavior, not masking
            ),
            core_max_keys_scanned=5,  # Core override - more restrictive
        )

        # Create event with many keys - should hit limit before finding all secrets
        event = {"data": {f"item{i}": {"secret": f"secret{i}"} for i in range(20)}}

        result = await redactor.redact(event)

        # Count how many secrets were actually redacted
        redacted_count = sum(
            1 for k, v in result["data"].items() if v.get("secret") == "***"
        )

        # Should have stopped before redacting all 20 (hit the scan limit)
        assert redacted_count < 20

    @pytest.mark.asyncio
    async def test_none_core_guardrail_uses_plugin_default(self) -> None:
        """When core guardrail is None, plugin default applies."""
        redactor = FieldMaskRedactor(
            config=FieldMaskConfig(
                fields_to_mask=["deep.nested.secret"],
                max_depth=16,  # Plugin default
            ),
            core_max_depth=None,  # No core override
        )

        # Create a structure that fits within plugin's default of 16
        event = {"deep": {"nested": {"secret": "sensitive_data"}}}

        result = await redactor.redact(event)

        # Should be redacted since depth 2 < plugin max_depth 16
        assert result["deep"]["nested"]["secret"] == "***"

    @pytest.mark.asyncio
    async def test_both_guardrails_respect_core_limits(self) -> None:
        """Both max_depth and max_keys_scanned honor core limits."""
        redactor = FieldMaskRedactor(
            config=FieldMaskConfig(
                fields_to_mask=["a.b.c.d.e.secret"],
                max_depth=20,
                max_keys_scanned=10000,
                on_guardrail_exceeded="warn",  # Test limit behavior, not masking
            ),
            core_max_depth=4,
            core_max_keys_scanned=10,
        )

        # depth 4 puts us at 'e', depth 5 is 'secret' - exceeds limit
        event = {"a": {"b": {"c": {"d": {"e": {"secret": "value"}}}}}}

        result = await redactor.redact(event)

        # Should NOT be redacted - depth exceeded
        assert result["a"]["b"]["c"]["d"]["e"]["secret"] == "value"


class TestRegexMaskGuardrails:
    """Tests for RegexMaskRedactor core guardrail behavior."""

    @pytest.mark.asyncio
    async def test_core_max_depth_overrides_plugin_when_more_restrictive(self) -> None:
        """Core max_depth=2 should override plugin default of 16."""
        redactor = RegexMaskRedactor(
            config=RegexMaskConfig(
                patterns=[r"level1\.level2\.level3\.secret"],
                max_depth=16,
            ),
            core_max_depth=2,
        )

        event = {"level1": {"level2": {"level3": {"secret": "sensitive_data"}}}}

        result = await redactor.redact(event)

        # Secret at depth 3 should NOT be redacted because core limit of 2 is exceeded
        assert result["level1"]["level2"]["level3"]["secret"] == "sensitive_data"

    @pytest.mark.asyncio
    async def test_plugin_max_depth_applies_when_more_restrictive_than_core(
        self,
    ) -> None:
        """Plugin max_depth=2 should apply when core allows max_depth=20."""
        redactor = RegexMaskRedactor(
            config=RegexMaskConfig(
                patterns=[r"level1\.level2\.level3\.secret"],
                max_depth=2,
            ),
            core_max_depth=20,
        )

        event = {"level1": {"level2": {"level3": {"secret": "sensitive_data"}}}}

        result = await redactor.redact(event)

        # Secret at depth 3 should NOT be redacted because plugin limit of 2 is exceeded
        assert result["level1"]["level2"]["level3"]["secret"] == "sensitive_data"

    @pytest.mark.asyncio
    async def test_core_max_keys_overrides_plugin_when_more_restrictive(self) -> None:
        """Core max_keys_scanned=5 should override plugin default of 1000."""
        redactor = RegexMaskRedactor(
            config=RegexMaskConfig(
                patterns=[r"data\.item\d+\.secret"],
                max_keys_scanned=1000,
            ),
            core_max_keys_scanned=5,
        )

        # Create event with many keys
        event = {"data": {f"item{i}": {"secret": f"secret{i}"} for i in range(20)}}

        result = await redactor.redact(event)

        # Count how many secrets were actually redacted
        redacted_count = sum(
            1 for k, v in result["data"].items() if v.get("secret") == "***"
        )

        # Should have stopped before redacting all 20
        assert redacted_count < 20

    @pytest.mark.asyncio
    async def test_none_core_guardrail_uses_plugin_default(self) -> None:
        """When core guardrail is None, plugin default applies."""
        redactor = RegexMaskRedactor(
            config=RegexMaskConfig(
                patterns=[r"nested\.secret"],
                max_depth=16,
            ),
            core_max_depth=None,
        )

        event = {"nested": {"secret": "sensitive_data"}}

        result = await redactor.redact(event)

        # Should be redacted since within plugin max_depth
        assert result["nested"]["secret"] == "***"


class TestGuardrailsIntegration:
    """Integration tests for guardrails being passed through the pipeline."""

    @pytest.mark.asyncio
    async def test_effective_depth_is_min_of_core_and_plugin(self) -> None:
        """Effective max_depth should be min(core, plugin)."""
        # Test case where core is more restrictive
        redactor1 = FieldMaskRedactor(
            config=FieldMaskConfig(fields_to_mask=["a.b.c"], max_depth=10),
            core_max_depth=5,
        )
        assert redactor1._max_depth == 5

        # Test case where plugin is more restrictive
        redactor2 = FieldMaskRedactor(
            config=FieldMaskConfig(fields_to_mask=["a.b.c"], max_depth=3),
            core_max_depth=10,
        )
        assert redactor2._max_depth == 3

        # Test case where they're equal
        redactor3 = FieldMaskRedactor(
            config=FieldMaskConfig(fields_to_mask=["a.b.c"], max_depth=5),
            core_max_depth=5,
        )
        assert redactor3._max_depth == 5

    @pytest.mark.asyncio
    async def test_effective_keys_scanned_is_min_of_core_and_plugin(self) -> None:
        """Effective max_keys_scanned should be min(core, plugin)."""
        # Test case where core is more restrictive
        redactor1 = FieldMaskRedactor(
            config=FieldMaskConfig(fields_to_mask=["a"], max_keys_scanned=1000),
            core_max_keys_scanned=100,
        )
        assert redactor1._max_scanned == 100

        # Test case where plugin is more restrictive
        redactor2 = FieldMaskRedactor(
            config=FieldMaskConfig(fields_to_mask=["a"], max_keys_scanned=50),
            core_max_keys_scanned=1000,
        )
        assert redactor2._max_scanned == 50


class TestConfigBuildersPassGuardrails:
    """Tests that config builders pass core guardrails to redactors."""

    def test_redactor_configs_includes_core_guardrails(self) -> None:
        """_redactor_configs should include core guardrails for field_mask/regex_mask."""
        from fapilog.core.config_builders import _redactor_configs
        from fapilog.core.settings import Settings

        # Create settings with custom core guardrails
        settings = Settings()
        settings.core.redaction_max_depth = 4
        settings.core.redaction_max_keys_scanned = 100

        configs = _redactor_configs(settings)

        # Verify field_mask gets core guardrails
        assert "core_max_depth" in configs["field_mask"]
        assert configs["field_mask"]["core_max_depth"] == 4
        assert "core_max_keys_scanned" in configs["field_mask"]
        assert configs["field_mask"]["core_max_keys_scanned"] == 100

        # Verify regex_mask gets core guardrails
        assert "core_max_depth" in configs["regex_mask"]
        assert configs["regex_mask"]["core_max_depth"] == 4
        assert "core_max_keys_scanned" in configs["regex_mask"]
        assert configs["regex_mask"]["core_max_keys_scanned"] == 100

    def test_redactor_configs_passes_none_when_guardrails_disabled(self) -> None:
        """_redactor_configs should pass None when core guardrails are None."""
        from fapilog.core.config_builders import _redactor_configs
        from fapilog.core.settings import Settings

        settings = Settings()
        settings.core.redaction_max_depth = None
        settings.core.redaction_max_keys_scanned = None

        configs = _redactor_configs(settings)

        assert configs["field_mask"]["core_max_depth"] is None
        assert configs["field_mask"]["core_max_keys_scanned"] is None
        assert configs["regex_mask"]["core_max_depth"] is None
        assert configs["regex_mask"]["core_max_keys_scanned"] is None
