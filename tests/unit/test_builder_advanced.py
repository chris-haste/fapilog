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


class TestWithFieldMask:
    """Tests for with_field_mask() method."""

    def test_with_field_mask_basic(self) -> None:
        """with_field_mask() configures field-based redaction."""
        builder = LoggerBuilder()

        result = builder.with_field_mask(fields=["password", "ssn", "credit_card"])

        assert result is builder  # Returns self for chaining
        assert "field_mask" in builder._config["core"]["redactors"]
        assert builder._config["redactor_config"]["field_mask"]["fields_to_mask"] == [
            "password",
            "ssn",
            "credit_card",
        ]
        assert builder._config["redactor_config"]["field_mask"]["mask_string"] == "***"

    def test_with_field_mask_custom_options(self) -> None:
        """with_field_mask() accepts custom mask and options."""
        builder = LoggerBuilder()

        builder.with_field_mask(
            fields=["password"],
            mask="[REDACTED]",
            block_on_failure=True,
            max_depth=10,
            max_keys=500,
        )

        config = builder._config["redactor_config"]["field_mask"]
        assert config["mask_string"] == "[REDACTED]"
        assert config["block_on_unredactable"] is True
        assert config["max_depth"] == 10
        assert config["max_keys_scanned"] == 500


class TestWithRegexMask:
    """Tests for with_regex_mask() method."""

    def test_with_regex_mask(self) -> None:
        """with_regex_mask() configures regex-based field path redaction."""
        builder = LoggerBuilder()

        result = builder.with_regex_mask(
            patterns=[r"(?i).*secret.*", r"(?i).*token.*"],
            mask="***",
        )

        assert result is builder  # Returns self for chaining
        assert "regex_mask" in builder._config["core"]["redactors"]
        config = builder._config["redactor_config"]["regex_mask"]
        assert config["patterns"] == [r"(?i).*secret.*", r"(?i).*token.*"]
        assert config["mask_string"] == "***"
        assert config["block_on_unredactable"] is False  # Default
        assert config["max_depth"] == 16  # Default
        assert config["max_keys_scanned"] == 1000  # Default


class TestWithUrlCredentialRedaction:
    """Tests for with_url_credential_redaction() method."""

    def test_with_url_credential_redaction_enable(self) -> None:
        """with_url_credential_redaction() enables URL credential scrubbing."""
        builder = LoggerBuilder()

        result = builder.with_url_credential_redaction(max_string_length=8192)

        assert result is builder  # Returns self for chaining
        assert "url_credentials" in builder._config["core"]["redactors"]
        config = builder._config["redactor_config"]["url_credentials"]
        assert config["max_string_length"] == 8192

    def test_with_url_credential_redaction_disable(self) -> None:
        """with_url_credential_redaction(enabled=False) disables the redactor."""
        builder = LoggerBuilder()

        # Enable first, then disable
        builder.with_url_credential_redaction(enabled=True)
        assert "url_credentials" in builder._config["core"]["redactors"]

        builder.with_url_credential_redaction(enabled=False)
        assert "url_credentials" not in builder._config["core"]["redactors"]


class TestWithRedactionGuardrails:
    """Tests for with_redaction_guardrails() method."""

    def test_with_redaction_guardrails(self) -> None:
        """with_redaction_guardrails() sets global redaction limits."""
        builder = LoggerBuilder()

        result = builder.with_redaction_guardrails(max_depth=10, max_keys=10000)

        assert result is builder  # Returns self for chaining
        assert builder._config["core"]["redaction_max_depth"] == 10
        assert builder._config["core"]["redaction_max_keys_scanned"] == 10000


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

        # Chain all methods together
        result = (
            builder.with_level("INFO")
            .with_preset("production")
            .add_stdout()
            .add_file("logs/backup")
            .with_routing(
                rules=[{"levels": ["ERROR"], "sinks": ["stdout_json"]}],
                fallback=["rotating_file"],
            )
            .with_field_mask(fields=["password"])
            .with_regex_mask(patterns=["(?i).*secret.*"])
            .with_url_credential_redaction()
            .with_redaction_guardrails(max_depth=8)
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
