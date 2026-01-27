"""Tests for LoggerBuilder advanced features (Story 10.26)."""

from __future__ import annotations

from fapilog.builder import LoggerBuilder


class TestWithRouting:
    """Tests for with_routing() method."""

    def test_with_routing_basic(self) -> None:
        """with_routing() configures sink routing with rules."""
        builder = LoggerBuilder()

        result = builder.with_routing(
            rules=[
                {"levels": ["ERROR", "WARNING"], "sinks": ["cloudwatch"]},
                {"levels": ["DEBUG", "INFO"], "sinks": ["rotating_file"]},
            ]
        )

        assert result is builder  # Returns self for chaining
        assert builder._config["sink_routing"]["enabled"] is True
        assert len(builder._config["sink_routing"]["rules"]) == 2
        assert builder._config["sink_routing"]["rules"][0]["levels"] == [
            "ERROR",
            "WARNING",
        ]
        assert builder._config["sink_routing"]["rules"][0]["sinks"] == ["cloudwatch"]
        assert builder._config["sink_routing"]["overlap"] is True  # Default

    def test_with_routing_fallback(self) -> None:
        """with_routing() accepts fallback sinks."""
        builder = LoggerBuilder()

        builder.with_routing(
            rules=[{"levels": ["ERROR"], "sinks": ["cloudwatch"]}],
            fallback=["rotating_file", "stdout_json"],
        )

        assert builder._config["sink_routing"]["fallback_sinks"] == [
            "rotating_file",
            "stdout_json",
        ]

    def test_with_routing_no_overlap(self) -> None:
        """with_routing() can disable rule overlap."""
        builder = LoggerBuilder()

        builder.with_routing(
            rules=[{"levels": ["ERROR"], "sinks": ["cloudwatch"]}],
            overlap=False,
        )

        assert builder._config["sink_routing"]["overlap"] is False


class TestUnifiedRedactionAPI:
    """Tests for unified with_redaction() API."""

    def test_with_redaction_fields_basic(self) -> None:
        """with_redaction(fields=...) configures field-based redaction."""
        builder = LoggerBuilder()

        result = builder.with_redaction(
            fields=["password", "ssn", "credit_card"],
            auto_prefix=False,
        )

        assert result is builder  # Returns self for chaining
        assert "field_mask" in builder._config["core"]["redactors"]
        assert builder._config["redactor_config"]["field_mask"]["fields_to_mask"] == [
            "password",
            "ssn",
            "credit_card",
        ]
        assert builder._config["redactor_config"]["field_mask"]["mask_string"] == "***"

    def test_with_redaction_auto_prefix(self) -> None:
        """with_redaction() auto-prefixes simple field names with data."""
        builder = LoggerBuilder()

        builder.with_redaction(fields=["password", "context.user_id"])

        fields = builder._config["redactor_config"]["field_mask"]["fields_to_mask"]
        assert "data.password" in fields  # Auto-prefixed
        assert "context.user_id" in fields  # Already has dot, not prefixed

    def test_with_redaction_custom_mask(self) -> None:
        """with_redaction() accepts custom mask and options."""
        builder = LoggerBuilder()

        builder.with_redaction(
            fields=["password"],
            mask="[REDACTED]",
            block_on_failure=True,
        )

        config = builder._config["redactor_config"]["field_mask"]
        assert config["mask_string"] == "[REDACTED]"
        assert config["block_on_unredactable"] is True

    def test_with_redaction_patterns(self) -> None:
        """with_redaction(patterns=...) configures regex-based redaction."""
        builder = LoggerBuilder()

        result = builder.with_redaction(
            patterns=[r"(?i).*secret.*", r"(?i).*token.*"],
        )

        assert result is builder  # Returns self for chaining
        assert "regex_mask" in builder._config["core"]["redactors"]
        config = builder._config["redactor_config"]["regex_mask"]
        assert config["patterns"] == [r"(?i).*secret.*", r"(?i).*token.*"]
        assert config["mask_string"] == "***"

    def test_with_redaction_url_credentials_enable(self) -> None:
        """with_redaction(url_credentials=True) enables URL credential scrubbing."""
        builder = LoggerBuilder()

        result = builder.with_redaction(url_credentials=True, url_max_length=8192)

        assert result is builder  # Returns self for chaining
        assert "url_credentials" in builder._config["core"]["redactors"]
        config = builder._config["redactor_config"]["url_credentials"]
        assert config["max_string_length"] == 8192

    def test_with_redaction_url_credentials_disable(self) -> None:
        """with_redaction(url_credentials=False) disables URL credential scrubbing."""
        builder = LoggerBuilder()

        # Enable first, then disable
        builder.with_redaction(url_credentials=True)
        assert "url_credentials" in builder._config["core"]["redactors"]

        builder.with_redaction(url_credentials=False)
        assert "url_credentials" not in builder._config["core"]["redactors"]

    def test_with_redaction_guardrails(self) -> None:
        """with_redaction(max_depth=..., max_keys=...) sets global limits."""
        builder = LoggerBuilder()

        result = builder.with_redaction(max_depth=10, max_keys=10000)

        assert result is builder  # Returns self for chaining
        assert builder._config["core"]["redaction_max_depth"] == 10
        assert builder._config["core"]["redaction_max_keys_scanned"] == 10000

    def test_with_redaction_preset_single(self) -> None:
        """with_redaction(preset=...) applies a single preset."""
        builder = LoggerBuilder()

        result = builder.with_redaction(preset="GDPR_PII")

        assert result is builder
        assert "field_mask" in builder._config["core"]["redactors"]
        fields = builder._config["redactor_config"]["field_mask"]["fields_to_mask"]
        assert "data.email" in fields

    def test_with_redaction_preset_multiple(self) -> None:
        """with_redaction(preset=[...]) applies multiple presets."""
        builder = LoggerBuilder()

        builder.with_redaction(preset=["GDPR_PII", "PCI_DSS"])

        fields = builder._config["redactor_config"]["field_mask"]["fields_to_mask"]
        # From GDPR_PII
        assert "data.email" in fields
        # From PCI_DSS
        assert "data.card_number" in fields


class TestConfigureEnricher:
    """Tests for configure_enricher() method."""

    def test_configure_enricher(self) -> None:
        """configure_enricher() sets enricher-specific configuration."""
        builder = LoggerBuilder()

        result = builder.configure_enricher(
            "runtime_info", service="my-api", env="prod"
        )

        assert result is builder  # Returns self for chaining
        assert builder._config["enricher_config"]["runtime_info"]["service"] == "my-api"
        assert builder._config["enricher_config"]["runtime_info"]["env"] == "prod"

    def test_configure_enricher_multiple(self) -> None:
        """configure_enricher() can configure multiple enrichers."""
        builder = LoggerBuilder()

        builder.configure_enricher("runtime_info", service="api")
        builder.configure_enricher("context_vars", include_request_id=True)

        assert builder._config["enricher_config"]["runtime_info"]["service"] == "api"
        assert (
            builder._config["enricher_config"]["context_vars"]["include_request_id"]
            is True
        )


class TestWithPlugins:
    """Tests for with_plugins() method."""

    def test_with_plugins_allowlist(self) -> None:
        """with_plugins() can restrict to an allowlist."""
        builder = LoggerBuilder()

        result = builder.with_plugins(
            allow_external=False,
            allowlist=["rotating_file", "stdout_json"],
        )

        assert result is builder  # Returns self for chaining
        assert builder._config["plugins"]["enabled"] is True
        assert builder._config["plugins"]["allow_external"] is False
        assert builder._config["plugins"]["allowlist"] == [
            "rotating_file",
            "stdout_json",
        ]

    def test_with_plugins_denylist(self) -> None:
        """with_plugins() can block plugins via denylist."""
        builder = LoggerBuilder()

        builder.with_plugins(denylist=["experimental_sink"])

        assert builder._config["plugins"]["denylist"] == ["experimental_sink"]

    def test_with_plugins_disable(self) -> None:
        """with_plugins(enabled=False) disables plugin loading."""
        builder = LoggerBuilder()

        builder.with_plugins(enabled=False)

        assert builder._config["plugins"]["enabled"] is False


class TestAdvancedFeaturesChainable:
    """Tests for AC5: All features chainable."""

    def test_advanced_features_chainable(self) -> None:
        """All advanced features integrate with basic builder methods."""
        builder = LoggerBuilder()

        # Chain all methods together using unified API
        result = (
            builder.with_level("INFO")
            .with_preset("production")
            .add_stdout()
            .add_file("logs/backup")
            .with_routing(
                rules=[{"levels": ["ERROR"], "sinks": ["stdout_json"]}],
                fallback=["rotating_file"],
            )
            .with_redaction(
                fields=["custom_password"],
                patterns=["(?i).*secret.*"],
                url_credentials=True,
                max_depth=8,
            )
            .configure_enricher("runtime_info", service="test-api")
            .with_plugins(allowlist=["rotating_file", "stdout_json"])
            .with_circuit_breaker(enabled=True)
        )

        # All methods return self for chaining
        assert result is builder

        # Verify configuration was accumulated
        assert builder._config["core"]["log_level"] == "INFO"
        assert builder._preset == "production"
        assert len(builder._sinks) == 2
        assert builder._config["sink_routing"]["enabled"] is True
        assert "field_mask" in builder._config["core"]["redactors"]
        assert "regex_mask" in builder._config["core"]["redactors"]
        assert "url_credentials" in builder._config["core"]["redactors"]
        assert builder._config["core"]["redaction_max_depth"] == 8
        assert (
            builder._config["enricher_config"]["runtime_info"]["service"] == "test-api"
        )
        assert builder._config["plugins"]["allowlist"] == [
            "rotating_file",
            "stdout_json",
        ]
        assert builder._config["core"]["sink_circuit_breaker_enabled"] is True


class TestStaticDiscoveryMethods:
    """Tests for static discovery methods on LoggerBuilder."""

    def test_list_redaction_presets(self) -> None:
        """list_redaction_presets() returns sorted list of preset names."""
        presets = LoggerBuilder.list_redaction_presets()

        assert isinstance(presets, list)
        assert "GDPR_PII" in presets
        assert "HIPAA_PHI" in presets
        assert "PCI_DSS" in presets
        assert "CREDENTIALS" in presets
        # Verify sorted
        assert presets == sorted(presets)

    def test_get_redaction_preset_info(self) -> None:
        """get_redaction_preset_info() returns preset metadata."""
        info = LoggerBuilder.get_redaction_preset_info("GDPR_PII")

        assert info["name"] == "GDPR_PII"
        assert "GDPR" in info["description"]
        assert "email" in info["fields"]
        assert len(info["patterns"]) > 0
        assert info["regulation"] == "GDPR"
        assert info["region"] == "EU"
        assert "gdpr" in info["tags"]

    def test_get_redaction_preset_info_unknown_raises(self) -> None:
        """get_redaction_preset_info() raises ValueError for unknown preset."""
        import pytest

        with pytest.raises(ValueError, match="Unknown redaction preset"):
            LoggerBuilder.get_redaction_preset_info("NONEXISTENT")
