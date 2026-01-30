"""Unit tests for builder processor methods (Story 10.25)."""

from fapilog.builder import LoggerBuilder


class TestWithSizeGuard:
    """Tests for with_size_guard() method."""

    def test_with_size_guard_adds_processor_and_config(self) -> None:
        """with_size_guard() adds 'size_guard' processor and sets config."""
        builder = LoggerBuilder()
        builder.with_size_guard(
            max_bytes="256 KB",
            action="truncate",
            preserve_fields=["level", "timestamp"],
        )

        processors = builder._config["core"]["processors"]
        processor_config = builder._config["processor_config"]["size_guard"]

        assert "size_guard" in processors
        assert processor_config["max_bytes"] == "256 KB"
        assert processor_config["action"] == "truncate"
        assert processor_config["preserve_fields"] == ["level", "timestamp"]

    def test_with_size_guard_accepts_int_bytes(self) -> None:
        """with_size_guard() accepts integer bytes value."""
        builder = LoggerBuilder()
        builder.with_size_guard(max_bytes=262144)

        processor_config = builder._config["processor_config"]["size_guard"]
        assert processor_config["max_bytes"] == 262144

    def test_with_size_guard_returns_self(self) -> None:
        """with_size_guard() returns self for chaining."""
        builder = LoggerBuilder()
        result = builder.with_size_guard()
        assert result is builder

    def test_with_size_guard_default_values(self) -> None:
        """with_size_guard() uses sensible defaults."""
        builder = LoggerBuilder()
        builder.with_size_guard()

        processor_config = builder._config["processor_config"]["size_guard"]

        assert processor_config["max_bytes"] == "256 KB"
        assert processor_config["action"] == "truncate"
        assert processor_config["preserve_fields"] == [
            "level",
            "timestamp",
            "logger",
            "correlation_id",
        ]

    def test_with_size_guard_action_options(self) -> None:
        """with_size_guard() accepts different action values."""
        for action in ["truncate", "drop", "warn"]:
            builder = LoggerBuilder()
            builder.with_size_guard(action=action)
            assert builder._config["processor_config"]["size_guard"]["action"] == action

    def test_with_size_guard_does_not_duplicate_processor(self) -> None:
        """Calling with_size_guard() twice doesn't duplicate processor."""
        builder = LoggerBuilder()
        builder.with_size_guard(max_bytes="128 KB")
        builder.with_size_guard(max_bytes="512 KB")

        processors = builder._config["core"]["processors"]
        assert processors.count("size_guard") == 1
        assert (
            builder._config["processor_config"]["size_guard"]["max_bytes"] == "512 KB"
        )

    def test_with_size_guard_creates_valid_logger(self) -> None:
        """with_size_guard() produces valid logger configuration."""
        logger = (
            LoggerBuilder()
            .with_size_guard(max_bytes="1 MB", action="truncate")
            .add_stdout()
            .build()
        )
        assert callable(logger.info)

    def test_with_size_guard_custom_preserve_fields(self) -> None:
        """with_size_guard() accepts custom preserve_fields list."""
        builder = LoggerBuilder()
        builder.with_size_guard(
            preserve_fields=["level", "timestamp", "correlation_id", "request_id"]
        )

        processor_config = builder._config["processor_config"]["size_guard"]
        assert processor_config["preserve_fields"] == [
            "level",
            "timestamp",
            "correlation_id",
            "request_id",
        ]

    def test_with_size_guard_enables_serialize_in_flush(self) -> None:
        """with_size_guard() automatically enables serialize_in_flush."""
        builder = LoggerBuilder()
        builder.with_size_guard(max_bytes="1 KB")

        core = builder._config.get("core", {})
        assert core.get("serialize_in_flush") is True

    def test_with_size_guard_respects_explicit_serialize_in_flush_false(self) -> None:
        """with_size_guard() respects pre-set serialize_in_flush=False."""
        builder = LoggerBuilder()
        # User explicitly disables serialize_in_flush first
        builder._config.setdefault("core", {})["serialize_in_flush"] = False
        builder.with_size_guard(max_bytes="1 KB")

        # Should stay False - user knows what they're doing
        assert builder._config["core"]["serialize_in_flush"] is False

    def test_with_size_guard_does_not_override_explicit_true(self) -> None:
        """with_size_guard() does not change pre-set serialize_in_flush=True."""
        builder = LoggerBuilder()
        # User explicitly enables serialize_in_flush first
        builder._config.setdefault("core", {})["serialize_in_flush"] = True
        builder.with_size_guard(max_bytes="1 KB")

        # Should remain True
        assert builder._config["core"]["serialize_in_flush"] is True
