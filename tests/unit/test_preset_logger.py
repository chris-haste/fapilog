"""Test preset parameter in get_logger and get_async_logger."""

import pytest

from fapilog import Settings, get_async_logger, get_logger


class TestGetLoggerWithPreset:
    """Test get_logger with preset parameter."""

    def test_preset_dev_creates_logger(self):
        """Dev preset creates a working logger with info method."""
        logger = get_logger(preset="dev")
        assert callable(logger.info)
        logger.info("test message")

    def test_preset_production_creates_logger(self):
        """Production preset creates a working logger with info method."""
        logger = get_logger(preset="production")
        assert callable(logger.info)

    def test_preset_fastapi_creates_logger(self):
        """FastAPI preset creates a working logger with info method."""
        logger = get_logger(preset="fastapi")
        assert callable(logger.info)

    def test_preset_minimal_creates_logger(self):
        """Minimal preset creates a working logger with info method."""
        logger = get_logger(preset="minimal")
        assert callable(logger.info)

    def test_invalid_preset_raises_value_error(self):
        """Invalid preset name raises ValueError."""
        with pytest.raises(ValueError, match="Invalid preset 'invalid'"):
            get_logger(preset="invalid")

    def test_preset_none_uses_default_behavior(self):
        """preset=None uses default/minimal behavior."""
        logger = get_logger(preset=None)
        assert callable(logger.info)

    def test_no_preset_uses_default_behavior(self):
        """No preset parameter uses default/minimal behavior."""
        logger = get_logger()
        assert callable(logger.info)


class TestAsyncLoggerWithPreset:
    """Test get_async_logger with preset parameter."""

    @pytest.mark.asyncio
    async def test_preset_fastapi_creates_async_logger(self):
        """FastAPI preset works with async logger."""
        logger = await get_async_logger(preset="fastapi")
        assert callable(logger.info)
        await logger.info("test message")

    @pytest.mark.asyncio
    async def test_preset_dev_creates_async_logger(self):
        """Dev preset works with async logger."""
        logger = await get_async_logger(preset="dev")
        assert callable(logger.info)

    @pytest.mark.asyncio
    async def test_invalid_preset_raises_value_error_async(self):
        """Invalid preset name raises ValueError in async context."""
        with pytest.raises(ValueError, match="Invalid preset 'bad'"):
            await get_async_logger(preset="bad")


class TestMutualExclusivity:
    """Test that preset and settings cannot be used together."""

    def test_preset_and_settings_raises_value_error(self):
        """Using both preset and settings raises ValueError."""
        with pytest.raises(ValueError, match="Cannot specify both"):
            get_logger(preset="production", settings=Settings())

    def test_error_message_is_helpful(self):
        """Error message guides users to choose one approach."""
        with pytest.raises(
            ValueError, match="Use preset for quick setup or settings for full control"
        ):
            get_logger(preset="dev", settings=Settings())

    @pytest.mark.asyncio
    async def test_async_preset_and_settings_raises_value_error(self):
        """Using both preset and settings raises ValueError in async."""
        with pytest.raises(ValueError, match="Cannot specify both"):
            await get_async_logger(preset="fastapi", settings=Settings())


class TestBackwardsCompatibility:
    """Test that existing code continues to work."""

    def test_settings_param_still_works(self):
        """Explicit settings parameter still works."""
        settings = Settings(core={"log_level": "DEBUG"})
        logger = get_logger(settings=settings)
        assert callable(logger.info)

    def test_sinks_param_still_works(self):
        """Explicit sinks parameter still works."""
        from fapilog.plugins.sinks.stdout_json import StdoutJsonSink

        logger = get_logger(sinks=[StdoutJsonSink()])
        assert callable(logger.info)

    def test_name_param_still_works(self):
        """Name parameter still works."""
        logger = get_logger(name="my-logger")
        assert callable(logger.info)

    def test_combined_name_and_preset(self):
        """Name and preset can be used together."""
        logger = get_logger(name="my-logger", preset="dev")
        assert callable(logger.info)


class TestFormatParameter:
    """Test format parameter validation."""

    def test_invalid_format_raises_value_error(self):
        """Unknown format values raise ValueError."""
        with pytest.raises(ValueError, match="Invalid format"):
            get_logger(format="xml")  # type: ignore[arg-type]

    def test_format_and_settings_raises_value_error(self):
        """format and settings are mutually exclusive."""
        with pytest.raises(
            ValueError, match="Cannot specify both 'format' and 'settings'"
        ):
            get_logger(format="pretty", settings=Settings())

    @pytest.mark.asyncio
    async def test_async_format_and_settings_raises_value_error(self):
        """format and settings are mutually exclusive in async."""
        with pytest.raises(
            ValueError, match="Cannot specify both 'format' and 'settings'"
        ):
            await get_async_logger(format="json", settings=Settings())
