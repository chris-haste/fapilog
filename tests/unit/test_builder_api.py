"""Unit tests for fluent builder API (Story 10.7)."""

import pytest


class TestLoggerBuilderBasic:
    """Test basic LoggerBuilder functionality."""

    def test_builder_exists_and_build_returns_logger(self):
        """LoggerBuilder can be instantiated and build() returns a logger."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        logger = builder.build()

        assert logger is not None
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "warning")


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

        logger = (
            LoggerBuilder()
            .with_name("test")
            .with_level("DEBUG")
            .build()
        )
        assert logger is not None
        assert hasattr(logger, "debug")


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
        assert logger is not None
        assert hasattr(logger, "debug")

    def test_preset_with_override(self):
        """Methods after preset override preset values."""
        from fapilog import LoggerBuilder

        # Dev preset sets DEBUG level, but we override to ERROR
        logger = (
            LoggerBuilder()
            .with_preset("dev")
            .with_level("ERROR")
            .build()
        )
        assert logger is not None

    def test_multiple_presets_raises_error(self):
        """Applying multiple presets raises ValueError."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder().with_preset("dev")
        with pytest.raises(ValueError, match="[Pp]reset already set"):
            builder.with_preset("production")


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
        assert logger is not None

    def test_add_file_with_string_size(self):
        """add_file() supports Story 10.4 string formats for max_bytes."""
        from fapilog import LoggerBuilder

        # Should accept "10 MB" string format
        logger = (
            LoggerBuilder()
            .add_file("/tmp/logs", max_bytes="10 MB")
            .build()
        )
        assert logger is not None

    def test_add_file_with_string_interval(self):
        """add_file() supports Story 10.4 string formats for interval."""
        from fapilog import LoggerBuilder

        # Should accept "daily" or "1h" string format
        logger = (
            LoggerBuilder()
            .add_file("/tmp/logs", interval="daily")
            .build()
        )
        assert logger is not None

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
        assert logger is not None

    def test_add_stdout_json_format(self):
        """add_stdout() with json format configures stdout_json sink."""
        from fapilog import LoggerBuilder

        logger = LoggerBuilder().add_stdout(format="json").build()
        assert logger is not None

    def test_add_stdout_pretty_convenience(self):
        """add_stdout_pretty() is convenience for pretty format."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        result = builder.add_stdout_pretty()
        assert result is builder


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
        assert logger is not None

    def test_add_http_with_timeout_string(self):
        """add_http() supports Story 10.4 timeout strings."""
        from fapilog import LoggerBuilder

        logger = (
            LoggerBuilder()
            .add_http("https://logs.example.com", timeout="30s")
            .build()
        )
        assert logger is not None

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
        assert logger is not None

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

        logger = (
            LoggerBuilder()
            .add_stdout()
            .add_file("/tmp/logs")
            .build()
        )
        assert logger is not None


class TestAsyncLoggerBuilder:
    """Test AsyncLoggerBuilder class."""

    @pytest.mark.asyncio
    async def test_async_builder_exists(self):
        """AsyncLoggerBuilder can be imported."""
        from fapilog import AsyncLoggerBuilder

        builder = AsyncLoggerBuilder()
        assert builder is not None

    @pytest.mark.asyncio
    async def test_build_async_creates_async_logger(self):
        """build_async() creates async logger."""
        from fapilog import AsyncLoggerBuilder

        logger = await AsyncLoggerBuilder().with_level("INFO").build_async()
        assert logger is not None
        assert hasattr(logger, "info")

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
        assert logger is not None


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
        assert logger is not None

    def test_with_redaction_patterns(self):
        """with_redaction() configures pattern redaction."""
        from fapilog import LoggerBuilder

        logger = (
            LoggerBuilder()
            .with_redaction(patterns=["secret.*", "token.*"])
            .build()
        )
        assert logger is not None


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
        assert logger is not None


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

        logger = (
            LoggerBuilder()
            .with_enrichers("runtime_info", "context_vars")
            .build()
        )
        assert logger is not None

    def test_with_filters_returns_self(self):
        """with_filters() returns self for chaining."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        result = builder.with_filters("level")
        assert result is builder

    def test_with_filters_configures_filters(self):
        """with_filters() configures filter plugins."""
        from fapilog import LoggerBuilder

        logger = (
            LoggerBuilder()
            .with_filters("level", "sampling")
            .build()
        )
        assert logger is not None


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
        assert logger is not None
