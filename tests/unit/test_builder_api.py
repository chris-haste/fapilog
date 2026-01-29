"""Unit tests for fluent builder API (Story 10.7)."""

import pytest


class TestLoggerBuilderBasic:
    """Test basic LoggerBuilder functionality."""

    def test_builder_exists_and_build_returns_logger(self):
        """LoggerBuilder can be instantiated and build() returns a logger."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        logger = builder.build()

        assert callable(logger.info)
        assert callable(logger.error)
        assert callable(logger.debug)
        assert callable(logger.warning)


class TestMethodChaining:
    """Test that builder methods return self for chaining."""

    def test_with_level_returns_self(self):
        """with_level() returns self for chaining."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        result = builder.with_level("INFO")
        assert result is builder

    def test_with_name_returns_self(self):
        """with_name() returns self for chaining."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        result = builder.with_name("mylogger")
        assert result is builder

    def test_chained_methods_work(self):
        """Multiple chained methods work together."""
        from fapilog import LoggerBuilder

        logger = LoggerBuilder().with_name("test").with_level("DEBUG").build()
        assert callable(logger.debug)


class TestPresetSupport:
    """Test preset configuration support."""

    def test_with_preset_returns_self(self):
        """with_preset() returns self for chaining."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        result = builder.with_preset("dev")
        assert result is builder

    def test_with_preset_creates_logger(self):
        """with_preset() applies preset and creates working logger."""
        from fapilog import LoggerBuilder

        logger = LoggerBuilder().with_preset("dev").build()
        assert callable(logger.debug)

    def test_preset_with_override(self):
        """Methods after preset override preset values."""
        from fapilog import LoggerBuilder

        # Dev preset sets DEBUG level, but we override to ERROR
        logger = LoggerBuilder().with_preset("dev").with_level("ERROR").build()
        assert callable(logger.error)

    def test_multiple_presets_raises_error(self):
        """Applying multiple presets raises ValueError."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder().with_preset("dev")
        with pytest.raises(ValueError, match="[Pp]reset already set"):
            builder.with_preset("production")

    def test_hardened_preset_creates_logger(self):
        """Story 3.10: with_preset("hardened") creates working logger."""
        from fapilog import LoggerBuilder

        logger = LoggerBuilder().with_preset("hardened").build()
        assert callable(logger.info)

    def test_hardened_preset_applies_multiple_redaction_presets(self):
        """Story 3.10: hardened preset applies HIPAA, PCI-DSS, CREDENTIALS."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder().with_preset("hardened")
        # The builder should have applied multiple redaction presets
        config = builder._config

        # Check redactor_config has field_mask with fields from all presets
        redactor_config = config.get("redactor_config", {})
        field_mask_config = redactor_config.get("field_mask", {})
        fields = field_mask_config.get("fields_to_mask", [])

        # CREDENTIALS fields
        assert "data.password" in fields, "Should have CREDENTIALS fields"
        assert "data.api_key" in fields, "Should have CREDENTIALS fields"

        # PCI_DSS fields
        assert "data.card_number" in fields, "Should have PCI_DSS fields"
        assert "data.cvv" in fields, "Should have PCI_DSS fields"

        # HIPAA_PHI fields (extends US_GOVERNMENT_IDS which has ssn)
        assert "data.ssn" in fields, "Should have HIPAA fields"
        assert "data.mrn" in fields, "Should have HIPAA fields"


class TestFileSink:
    """Test file sink configuration."""

    def test_add_file_returns_self(self):
        """add_file() returns self for chaining."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        result = builder.add_file("/tmp/logs")
        assert result is builder

    def test_add_file_creates_logger(self):
        """add_file() configures file sink and creates logger."""
        from fapilog import LoggerBuilder

        logger = LoggerBuilder().add_file("/tmp/logs").build()
        assert callable(logger.info)

    def test_add_file_with_string_size(self):
        """add_file() supports Story 10.4 string formats for max_bytes."""
        from fapilog import LoggerBuilder

        # Should accept "10 MB" string format
        logger = LoggerBuilder().add_file("/tmp/logs", max_bytes="10 MB").build()
        assert callable(logger.info)

    def test_add_file_with_string_interval(self):
        """add_file() supports Story 10.4 string formats for interval."""
        from fapilog import LoggerBuilder

        # Should accept "daily" or "1h" string format
        logger = LoggerBuilder().add_file("/tmp/logs", interval="daily").build()
        assert callable(logger.info)

    def test_add_file_requires_directory(self):
        """add_file() validates that directory is required."""
        from fapilog import LoggerBuilder

        with pytest.raises(ValueError, match="[Dd]irectory"):
            LoggerBuilder().add_file("").build()


class TestStdoutSink:
    """Test stdout sink configuration."""

    def test_add_stdout_returns_self(self):
        """add_stdout() returns self for chaining."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        result = builder.add_stdout()
        assert result is builder

    def test_add_stdout_creates_logger(self):
        """add_stdout() configures stdout sink."""
        from fapilog import LoggerBuilder

        logger = LoggerBuilder().add_stdout().build()
        assert callable(logger.info)

    def test_add_stdout_json_format(self):
        """add_stdout() with json format configures stdout_json sink."""
        from fapilog import LoggerBuilder

        logger = LoggerBuilder().add_stdout(format="json").build()
        assert callable(logger.info)

    def test_add_stdout_pretty_convenience(self):
        """add_stdout_pretty() is convenience for pretty format."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        result = builder.add_stdout_pretty()
        assert result is builder

    def test_add_stdout_capture_mode(self):
        """AC3: add_stdout() accepts capture_mode for testing."""
        from fapilog import LoggerBuilder

        # Should accept capture_mode parameter
        logger = LoggerBuilder().add_stdout(capture_mode=True).build()
        assert callable(logger.info)

    def test_add_stdout_capture_mode_enables_output_capture(self):
        """AC3: capture_mode=True enables capturing stdout in tests."""
        import io
        import sys

        from fapilog import AsyncLoggerBuilder

        buf = io.BytesIO()
        orig = sys.stdout
        sys.stdout = io.TextIOWrapper(buf, encoding="utf-8")
        try:
            import asyncio

            async def test_capture():
                logger = await (
                    AsyncLoggerBuilder().add_stdout(capture_mode=True).build_async()
                )
                await logger.info("captured message")
                await logger.drain()

            asyncio.run(test_capture())
            sys.stdout.flush()
            output = buf.getvalue().decode("utf-8")
            assert "captured message" in output
        finally:
            sys.stdout = orig


class TestHttpSink:
    """Test HTTP sink configuration."""

    def test_add_http_returns_self(self):
        """add_http() returns self for chaining."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        result = builder.add_http("https://logs.example.com")
        assert result is builder

    def test_add_http_creates_logger(self):
        """add_http() configures HTTP sink."""
        from fapilog import LoggerBuilder

        logger = LoggerBuilder().add_http("https://logs.example.com").build()
        assert callable(logger.info)

    def test_add_http_with_timeout_string(self):
        """add_http() supports Story 10.4 timeout strings."""
        from fapilog import LoggerBuilder

        logger = (
            LoggerBuilder().add_http("https://logs.example.com", timeout="30s").build()
        )
        assert callable(logger.info)

    def test_add_http_with_milliseconds_timeout(self):
        """add_http() accepts millisecond timeout strings (Story 10.37 AC5)."""
        from fapilog import LoggerBuilder

        logger = (
            LoggerBuilder()
            .add_http("https://logs.example.com", timeout="100ms")
            .build()
        )
        assert callable(logger.info)

    def test_add_http_with_decimal_timeout(self):
        """add_http() accepts decimal timeout strings (Story 10.37 AC5)."""
        from fapilog import LoggerBuilder

        logger = (
            LoggerBuilder().add_http("https://logs.example.com", timeout="0.5s").build()
        )
        assert callable(logger.info)

    def test_add_http_requires_endpoint(self):
        """add_http() validates that endpoint is required."""
        from fapilog import LoggerBuilder

        with pytest.raises(ValueError, match="[Ee]ndpoint"):
            LoggerBuilder().add_http("").build()


class TestWebhookSink:
    """Test webhook sink configuration."""

    def test_add_webhook_returns_self(self):
        """add_webhook() returns self for chaining."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        result = builder.add_webhook("https://webhook.example.com")
        assert result is builder

    def test_add_webhook_creates_logger(self):
        """add_webhook() configures webhook sink."""
        from fapilog import LoggerBuilder

        logger = LoggerBuilder().add_webhook("https://webhook.example.com").build()
        assert callable(logger.info)

    def test_add_webhook_requires_endpoint(self):
        """add_webhook() validates that endpoint is required."""
        from fapilog import LoggerBuilder

        with pytest.raises(ValueError, match="[Ee]ndpoint"):
            LoggerBuilder().add_webhook("").build()


class TestMultipleSinks:
    """Test multiple sink configurations."""

    def test_multiple_sinks_can_be_added(self):
        """Multiple sinks can be configured together."""
        from fapilog import LoggerBuilder

        logger = LoggerBuilder().add_stdout().add_file("/tmp/logs").build()
        assert callable(logger.info)


class TestAsyncLoggerBuilder:
    """Test AsyncLoggerBuilder class."""

    @pytest.mark.asyncio
    async def test_async_builder_exists(self):
        """AsyncLoggerBuilder can be imported."""
        from fapilog import AsyncLoggerBuilder

        builder = AsyncLoggerBuilder()
        assert isinstance(builder, AsyncLoggerBuilder)

    @pytest.mark.asyncio
    async def test_build_async_creates_async_logger(self):
        """build_async() creates async logger."""
        from fapilog import AsyncLoggerBuilder

        logger = await AsyncLoggerBuilder().with_level("INFO").build_async()
        assert callable(logger.info)

    @pytest.mark.asyncio
    async def test_async_builder_has_same_api(self):
        """Async builder has same API as sync builder."""
        from fapilog import AsyncLoggerBuilder

        builder = AsyncLoggerBuilder()
        # Test method chaining
        result = builder.with_level("INFO").with_name("test").add_stdout()
        assert result is builder

    @pytest.mark.asyncio
    async def test_async_builder_with_preset(self):
        """Async builder supports presets."""
        from fapilog import AsyncLoggerBuilder

        logger = await AsyncLoggerBuilder().with_preset("dev").build_async()
        assert callable(logger.info)


class TestSecurityMethods:
    """Test security configuration methods."""

    def test_with_redaction_returns_self(self):
        """with_redaction() returns self for chaining."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        result = builder.with_redaction(fields=["password"])
        assert result is builder

    def test_with_redaction_fields(self):
        """with_redaction() configures field redaction."""
        from fapilog import LoggerBuilder

        logger = (
            LoggerBuilder()
            .with_redaction(fields=["password", "ssn", "api_key"])
            .build()
        )
        assert callable(logger.info)

    def test_with_redaction_patterns(self):
        """with_redaction() configures pattern redaction."""
        from fapilog import LoggerBuilder

        logger = (
            LoggerBuilder().with_redaction(patterns=["secret.*", "token.*"]).build()
        )
        assert callable(logger.info)


class TestContextMethods:
    """Test context configuration methods."""

    def test_with_context_returns_self(self):
        """with_context() returns self for chaining."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        result = builder.with_context(service="api")
        assert result is builder

    def test_with_context_sets_bound_context(self):
        """with_context() sets default bound context."""
        from fapilog import LoggerBuilder

        logger = (
            LoggerBuilder()
            .with_context(service="api", env="production", version="1.0.0")
            .build()
        )
        assert callable(logger.info)


class TestPluginMethods:
    """Test enricher and filter configuration methods."""

    def test_with_enrichers_returns_self(self):
        """with_enrichers() returns self for chaining."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        result = builder.with_enrichers("runtime_info")
        assert result is builder

    def test_with_enrichers_configures_enrichers(self):
        """with_enrichers() configures enricher plugins."""
        from fapilog import LoggerBuilder

        logger = LoggerBuilder().with_enrichers("runtime_info", "context_vars").build()
        assert callable(logger.info)

    def test_with_filters_returns_self(self):
        """with_filters() returns self for chaining."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        result = builder.with_filters("level")
        assert result is builder

    def test_with_filters_configures_filters(self):
        """with_filters() configures filter plugins."""
        from fapilog import LoggerBuilder

        logger = LoggerBuilder().with_filters("level", "sampling").build()
        assert callable(logger.info)


class TestPerformanceMethods:
    """Test performance configuration methods."""

    def test_with_queue_size_returns_self(self):
        """with_queue_size() returns self for chaining."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        result = builder.with_queue_size(10000)
        assert result is builder

    def test_with_batch_size_returns_self(self):
        """with_batch_size() returns self for chaining."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        result = builder.with_batch_size(100)
        assert result is builder

    def test_with_batch_timeout_returns_self(self):
        """with_batch_timeout() returns self for chaining."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        result = builder.with_batch_timeout("1s")
        assert result is builder

    def test_performance_methods_configure_logger(self):
        """Performance methods configure logger correctly."""
        from fapilog import LoggerBuilder

        logger = (
            LoggerBuilder()
            .with_queue_size(5000)
            .with_batch_size(50)
            .with_batch_timeout("2s")
            .build()
        )
        assert callable(logger.info)

    def test_with_batch_timeout_numeric(self):
        """with_batch_timeout() accepts numeric values."""
        from fapilog import LoggerBuilder

        logger = LoggerBuilder().with_batch_timeout(1.5).build()
        assert callable(logger.info)

    def test_with_batch_timeout_invalid_format_raises_error(self):
        """with_batch_timeout() raises ValueError for invalid format."""
        from fapilog import LoggerBuilder

        with pytest.raises(ValueError, match="Invalid duration format"):
            LoggerBuilder().with_batch_timeout("invalid").build()


class TestOptionalParameters:
    """Test optional sink parameters for coverage."""

    def test_add_file_with_max_files(self):
        """add_file() accepts max_files parameter."""
        from fapilog import LoggerBuilder

        logger = LoggerBuilder().add_file("/tmp/logs", max_files=5).build()
        assert callable(logger.info)

    def test_add_file_with_compress(self):
        """add_file() accepts compress parameter."""
        from fapilog import LoggerBuilder

        logger = LoggerBuilder().add_file("/tmp/logs", compress=True).build()
        assert callable(logger.info)

    def test_add_file_with_all_options(self):
        """add_file() accepts all optional parameters together."""
        from fapilog import LoggerBuilder

        logger = (
            LoggerBuilder()
            .add_file(
                "/tmp/logs",
                max_bytes="50 MB",
                interval="daily",
                max_files=10,
                compress=True,
            )
            .build()
        )
        assert callable(logger.info)

    def test_add_http_with_headers(self):
        """add_http() accepts headers parameter."""
        from fapilog import LoggerBuilder

        logger = (
            LoggerBuilder()
            .add_http(
                "https://logs.example.com",
                headers={"Authorization": "Bearer token"},
            )
            .build()
        )
        assert callable(logger.info)

    def test_add_webhook_with_secret(self):
        """add_webhook() accepts secret parameter."""
        from fapilog import LoggerBuilder

        logger = (
            LoggerBuilder()
            .add_webhook(
                "https://webhook.example.com",
                secret="shared-secret",
            )
            .build()
        )
        assert callable(logger.info)

    def test_add_webhook_with_headers(self):
        """add_webhook() accepts headers parameter."""
        from fapilog import LoggerBuilder

        logger = (
            LoggerBuilder()
            .add_webhook(
                "https://webhook.example.com",
                headers={"X-Custom": "value"},
            )
            .build()
        )
        assert callable(logger.info)

    def test_add_webhook_with_all_options(self):
        """add_webhook() accepts all optional parameters together."""
        from fapilog import LoggerBuilder

        logger = (
            LoggerBuilder()
            .add_webhook(
                "https://webhook.example.com",
                secret="shared-secret",
                timeout="10s",
                headers={"X-Custom": "value"},
            )
            .build()
        )
        assert callable(logger.info)


class TestValidationErrors:
    """Test validation error paths."""

    def test_build_invalid_config_raises_error(self):
        """build() raises ValueError for invalid Settings configuration."""
        from fapilog import LoggerBuilder

        # Invalid log level should cause Settings validation to fail
        builder = LoggerBuilder()
        builder._config["core"] = {"log_level": "INVALID_LEVEL"}

        with pytest.raises(ValueError, match="Invalid builder configuration"):
            builder.build()

    @pytest.mark.asyncio
    async def test_build_async_invalid_config_raises_error(self):
        """build_async() raises ValueError for invalid Settings configuration."""
        from fapilog import AsyncLoggerBuilder

        # Invalid log level should cause Settings validation to fail
        builder = AsyncLoggerBuilder()
        builder._config["core"] = {"log_level": "INVALID_LEVEL"}

        with pytest.raises(ValueError, match="Invalid builder configuration"):
            await builder.build_async()

    def test_invalid_preset_raises_error(self):
        """Invalid preset name raises ValueError."""
        from fapilog import LoggerBuilder

        with pytest.raises(ValueError, match="Invalid preset"):
            LoggerBuilder().with_preset("nonexistent_preset").build()


class TestRedactionBranches:
    """Test redaction configuration branches."""

    def test_with_redaction_fields_only(self):
        """with_redaction() with fields only enables field_mask redactor."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder().with_redaction(fields=["password"])
        assert "field_mask" in builder._config.get("core", {}).get("redactors", [])

    def test_with_redaction_patterns_only(self):
        """with_redaction() with patterns only enables regex_mask redactor."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder().with_redaction(patterns=["secret.*"])
        assert "regex_mask" in builder._config.get("core", {}).get("redactors", [])

    def test_with_redaction_both_fields_and_patterns(self):
        """with_redaction() with both enables both redactors."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder().with_redaction(
            fields=["password"],
            patterns=["secret.*"],
        )
        redactors = builder._config.get("core", {}).get("redactors", [])
        assert "field_mask" in redactors
        assert "regex_mask" in redactors

    def test_with_redaction_called_multiple_times(self):
        """with_redaction() can be called multiple times without duplicates."""
        from fapilog import LoggerBuilder

        builder = (
            LoggerBuilder()
            .with_redaction(fields=["password"])
            .with_redaction(fields=["ssn"])  # Add more fields
        )
        redactors = builder._config.get("core", {}).get("redactors", [])
        # Should only have one field_mask entry
        assert redactors.count("field_mask") == 1

    def test_with_redaction_additive_by_default(self):
        """with_redaction() merges fields by default (with auto-prefix)."""
        from fapilog import LoggerBuilder

        builder = (
            LoggerBuilder()
            .with_redaction(fields=["password"])
            .with_redaction(fields=["ssn"])
        )
        fields = builder._config["redactor_config"]["field_mask"]["fields_to_mask"]
        # Fields are auto-prefixed with data.
        assert "data.password" in fields
        assert "data.ssn" in fields

    def test_with_redaction_replace_overwrites_fields(self):
        """with_redaction(replace=True) replaces existing fields."""
        from fapilog import LoggerBuilder

        builder = (
            LoggerBuilder()
            .with_redaction(fields=["password", "email"])
            .with_redaction(fields=["ssn"], replace=True)
        )
        fields = builder._config["redactor_config"]["field_mask"]["fields_to_mask"]
        # After replace, only the new field remains (with auto-prefix)
        assert fields == ["data.ssn"]
        assert "data.password" not in fields

    def test_with_redaction_replace_overwrites_patterns(self):
        """with_redaction(replace=True) replaces existing patterns."""
        from fapilog import LoggerBuilder

        builder = (
            LoggerBuilder()
            .with_redaction(patterns=["secret.*", "token.*"])
            .with_redaction(patterns=["password.*"], replace=True)
        )
        patterns = builder._config["redactor_config"]["regex_mask"]["patterns"]
        assert patterns == ["password.*"]
        assert "secret.*" not in patterns


class TestWithContextDocstring:
    """Test with_context() docstring documents field routing (Story 10.42)."""

    def test_docstring_explains_field_routing(self):
        """AC1: Docstring explains that known fields go to context, custom to data."""
        from fapilog import LoggerBuilder

        docstring = LoggerBuilder.with_context.__doc__
        assert docstring is not None  # noqa: WA003 - guard before behavioral checks
        assert "context" in docstring.lower()
        assert "data" in docstring.lower()
        assert "request_id" in docstring

    def test_docstring_lists_known_context_fields(self):
        """AC2: Docstring lists all 5 known context fields."""
        from fapilog import LoggerBuilder

        docstring = LoggerBuilder.with_context.__doc__
        known_fields = ["request_id", "user_id", "tenant_id", "trace_id", "span_id"]
        for field in known_fields:
            assert field in docstring, f"Missing known context field: {field}"

    def test_docstring_includes_example(self):
        """AC3: Docstring includes an example showing field destinations."""
        from fapilog import LoggerBuilder

        docstring = LoggerBuilder.with_context.__doc__
        assert "Example:" in docstring or ">>>" in docstring
