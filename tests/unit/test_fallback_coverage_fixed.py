"""Comprehensive tests for fapilog.core.fallback module."""

import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch
from typing import Any

import pytest

from fapilog.core.fallback import (
    FallbackStrategy,
    FallbackTrigger,
    FallbackConfig,
    FallbackStats,
    FallbackError,
    FallbackProvider,
    StaticValueFallback,
    FunctionFallback,
    CacheFallback,
    ChainedFallback,
    AsyncFallbackWrapper,
    FallbackManager,
    fallback,
)
from fapilog.core.errors import ErrorCategory, ErrorSeverity, FapilogError


class TestFallbackEnums:
    """Test fallback enums and constants."""

    def test_fallback_strategy_enum(self):
        """Test FallbackStrategy enum values."""
        assert FallbackStrategy.STATIC_VALUE == "static_value"
        assert FallbackStrategy.FUNCTION_CALL == "function_call"
        assert FallbackStrategy.CACHE_LOOKUP == "cache_lookup"
        assert FallbackStrategy.DEGRADED_SERVICE == "degraded_service"
        assert FallbackStrategy.CIRCUIT_BREAKER == "circuit_breaker"
        assert FallbackStrategy.CHAIN == "chain"

    def test_fallback_trigger_enum(self):
        """Test FallbackTrigger enum values."""
        assert FallbackTrigger.EXCEPTION == "exception"
        assert FallbackTrigger.TIMEOUT == "timeout"
        assert FallbackTrigger.CIRCUIT_OPEN == "circuit_open"
        assert FallbackTrigger.HIGH_LATENCY == "high_latency"
        assert FallbackTrigger.RATE_LIMIT == "rate_limit"
        assert FallbackTrigger.CUSTOM == "custom"


class TestFallbackConfig:
    """Test FallbackConfig dataclass."""

    def test_fallback_config_defaults(self):
        """Test FallbackConfig default values."""
        config = FallbackConfig()
        assert config.strategy == FallbackStrategy.STATIC_VALUE
        assert config.triggers == [FallbackTrigger.EXCEPTION, FallbackTrigger.TIMEOUT]
        assert config.timeout is None
        assert config.latency_threshold is None
        assert config.static_value is None
        assert config.fallback_function is None
        assert config.cache_key_generator is None
        assert config.cache_ttl is None
        assert config.track_fallback_usage is True
        assert config.log_fallback_events is True

    def test_fallback_config_custom_values(self):
        """Test FallbackConfig with custom values."""

        async def dummy_function():
            return "fallback"

        def key_generator(*args):
            return "cache_key"

        config = FallbackConfig(
            strategy=FallbackStrategy.FUNCTION_CALL,
            triggers=[FallbackTrigger.HIGH_LATENCY],
            timeout=5.0,
            latency_threshold=2.0,
            static_value="default",
            fallback_function=dummy_function,
            cache_key_generator=key_generator,
            cache_ttl=300.0,
            track_fallback_usage=False,
            log_fallback_events=False,
        )

        assert config.strategy == FallbackStrategy.FUNCTION_CALL
        assert config.triggers == [FallbackTrigger.HIGH_LATENCY]
        assert config.timeout == 5.0
        assert config.latency_threshold == 2.0
        assert config.static_value == "default"
        assert config.fallback_function == dummy_function
        assert config.cache_key_generator == key_generator
        assert config.cache_ttl == 300.0
        assert config.track_fallback_usage is False
        assert config.log_fallback_events is False

    def test_fallback_config_empty_triggers(self):
        """Test FallbackConfig with empty triggers sets defaults."""
        config = FallbackConfig(triggers=[])
        # __post_init__ should set default triggers
        assert config.triggers == [FallbackTrigger.EXCEPTION, FallbackTrigger.TIMEOUT]


class TestFallbackStats:
    """Test FallbackStats dataclass."""

    def test_fallback_stats_defaults(self):
        """Test FallbackStats default values."""
        stats = FallbackStats()
        assert stats.total_calls == 0
        assert stats.fallback_calls == 0
        assert stats.primary_success == 0
        assert stats.fallback_success == 0
        assert stats.fallback_failures == 0
        assert stats.average_primary_latency == 0.0
        assert stats.average_fallback_latency == 0.0
        # trigger_counts is initialized in __post_init__
        assert len(stats.trigger_counts) == len(FallbackTrigger)

    def test_fallback_stats_custom_values(self):
        """Test FallbackStats with custom values."""
        stats = FallbackStats(
            total_calls=100,
            fallback_calls=20,
            primary_success=80,
            fallback_success=15,
            fallback_failures=5,
            average_primary_latency=0.5,
            average_fallback_latency=0.2,
        )

        assert stats.total_calls == 100
        assert stats.fallback_calls == 20
        assert stats.primary_success == 80
        assert stats.fallback_success == 15
        assert stats.fallback_failures == 5
        assert stats.average_primary_latency == 0.5
        assert stats.average_fallback_latency == 0.2

    def test_fallback_stats_primary_success_rate_property(self):
        """Test FallbackStats primary_success_rate property."""
        stats = FallbackStats(total_calls=100, primary_success=80, fallback_calls=20)
        assert (
            stats.primary_success_rate == 1.0
        )  # 80 successes out of 80 primary attempts

        # Test zero division
        empty_stats = FallbackStats()
        assert empty_stats.primary_success_rate == 0.0

    def test_fallback_stats_fallback_rate_property(self):
        """Test FallbackStats fallback_rate property."""
        stats = FallbackStats(total_calls=100, fallback_calls=20)
        assert stats.fallback_rate == 0.2

        # Test zero division
        empty_stats = FallbackStats()
        assert empty_stats.fallback_rate == 0.0


class TestFallbackError:
    """Test FallbackError exception class."""

    def test_fallback_error_basic(self):
        """Test basic FallbackError creation."""
        error = FallbackError("Fallback failed")
        assert str(error) == "Fallback failed"
        # FallbackError inherits from FapilogError, so check its attributes
        assert hasattr(error, "primary_error")
        assert hasattr(error, "fallback_error")

    def test_fallback_error_with_errors(self):
        """Test FallbackError with primary and fallback errors."""
        primary_error = ValueError("Primary failed")
        fallback_error = RuntimeError("Fallback failed")

        error = FallbackError(
            "All operations failed",
            primary_error=primary_error,
            fallback_error=fallback_error,
        )

        assert str(error) == "All operations failed"
        assert error.primary_error == primary_error
        assert error.fallback_error == fallback_error


class TestStaticValueFallback:
    """Test StaticValueFallback provider."""

    @pytest.mark.asyncio
    async def test_static_value_fallback_success(self):
        """Test StaticValueFallback returns static value."""
        provider = StaticValueFallback("fallback_value")
        result = await provider.provide_fallback("arg1", kwarg1="value1")
        assert result == "fallback_value"

    @pytest.mark.asyncio
    async def test_static_value_fallback_none(self):
        """Test StaticValueFallback with None value."""
        provider = StaticValueFallback(None)
        result = await provider.provide_fallback()
        assert result is None

    @pytest.mark.asyncio
    async def test_static_value_fallback_complex_object(self):
        """Test StaticValueFallback with complex object."""
        fallback_obj = {"key": "value", "nested": {"data": 123}}
        provider = StaticValueFallback(fallback_obj)
        result = await provider.provide_fallback()
        assert result == fallback_obj


class TestFunctionFallback:
    """Test FunctionFallback provider."""

    @pytest.mark.asyncio
    async def test_function_fallback_success(self):
        """Test FunctionFallback calls function successfully."""

        async def fallback_func(*args, **kwargs):
            return f"fallback: {args}, {kwargs}"

        provider = FunctionFallback(fallback_func)
        result = await provider.provide_fallback("arg1", kwarg1="value1")
        assert result == "fallback: ('arg1',), {'kwarg1': 'value1'}"

    @pytest.mark.asyncio
    async def test_function_fallback_exception(self):
        """Test FunctionFallback handles function exceptions."""

        async def failing_fallback():
            raise ValueError("Fallback function failed")

        provider = FunctionFallback(failing_fallback)

        with pytest.raises(ValueError, match="Fallback function failed"):
            await provider.provide_fallback()


class TestCacheFallback:
    """Test CacheFallback provider."""

    @pytest.mark.asyncio
    async def test_cache_fallback_hit(self):
        """Test CacheFallback returns cached value."""
        cache = {"key1": "cached_value"}

        def key_generator(*args, **kwargs):
            return args[0] if args else "default"

        provider = CacheFallback(cache, key_generator)

        result = await provider.provide_fallback("key1")
        assert result == "cached_value"

    @pytest.mark.asyncio
    async def test_cache_fallback_miss_with_default(self):
        """Test CacheFallback returns default on cache miss."""
        cache = {"key1": "value1"}

        def key_generator(*args, **kwargs):
            return args[0] if args else "default"

        provider = CacheFallback(cache, key_generator, default_value="default_fallback")

        result = await provider.provide_fallback("missing_key")
        assert result == "default_fallback"

    @pytest.mark.asyncio
    async def test_cache_fallback_miss_no_default(self):
        """Test CacheFallback returns None on cache miss without default."""
        cache = {"key1": "value1"}

        def key_generator(*args, **kwargs):
            return args[0] if args else "default"

        provider = CacheFallback(cache, key_generator)

        result = await provider.provide_fallback("missing_key")
        assert result is None


class TestChainedFallback:
    """Test ChainedFallback provider."""

    @pytest.mark.asyncio
    async def test_chained_fallback_first_success(self):
        """Test ChainedFallback uses first successful provider."""
        provider1 = StaticValueFallback("first")
        provider2 = StaticValueFallback("second")

        chained = ChainedFallback([provider1, provider2])
        result = await chained.provide_fallback()
        assert result == "first"

    @pytest.mark.asyncio
    async def test_chained_fallback_second_success(self):
        """Test ChainedFallback falls through to second provider."""

        async def failing_provider(*args, **kwargs):
            raise ValueError("First provider failed")

        provider1 = FunctionFallback(failing_provider)
        provider2 = StaticValueFallback("second")

        chained = ChainedFallback([provider1, provider2])
        result = await chained.provide_fallback()
        assert result == "second"

    @pytest.mark.asyncio
    async def test_chained_fallback_all_fail(self):
        """Test ChainedFallback when all providers fail."""

        async def failing_provider1(*args, **kwargs):
            raise ValueError("First failed")

        async def failing_provider2(*args, **kwargs):
            raise RuntimeError("Second failed")

        provider1 = FunctionFallback(failing_provider1)
        provider2 = FunctionFallback(failing_provider2)

        chained = ChainedFallback([provider1, provider2])

        with pytest.raises(FallbackError, match="All fallback providers failed"):
            await chained.provide_fallback()

    @pytest.mark.asyncio
    async def test_chained_fallback_empty_providers(self):
        """Test ChainedFallback with empty providers list."""
        chained = ChainedFallback([])

        with pytest.raises(FallbackError, match="All fallback providers failed"):
            await chained.provide_fallback()


class TestAsyncFallbackWrapper:
    """Test AsyncFallbackWrapper class."""

    @pytest.mark.asyncio
    async def test_wrapper_primary_success(self):
        """Test wrapper executes primary function successfully."""

        async def primary_func(*args, **kwargs):
            return f"primary: {args}, {kwargs}"

        provider = StaticValueFallback("fallback")
        wrapper = AsyncFallbackWrapper("test", provider)

        result = await wrapper.execute(primary_func, "arg1", kwarg1="value1")
        assert result == "primary: ('arg1',), {'kwarg1': 'value1'}"

    @pytest.mark.asyncio
    async def test_wrapper_fallback_on_exception(self):
        """Test wrapper uses fallback on primary function exception."""

        async def failing_primary():
            raise ValueError("Primary failed")

        config = FallbackConfig(triggers=[FallbackTrigger.EXCEPTION])
        provider = StaticValueFallback("fallback_value")
        wrapper = AsyncFallbackWrapper("test", provider, config)

        result = await wrapper.execute(failing_primary)
        assert result == "fallback_value"

    @pytest.mark.asyncio
    async def test_wrapper_stats_tracking(self):
        """Test wrapper tracks statistics."""

        async def primary_func():
            return "primary_result"

        config = FallbackConfig(track_fallback_usage=True)
        provider = StaticValueFallback("fallback")
        wrapper = AsyncFallbackWrapper("test", provider, config)

        # Call multiple times
        await wrapper.execute(primary_func)
        await wrapper.execute(primary_func)

        stats = wrapper.stats
        assert stats.total_calls == 2
        assert stats.primary_success == 2
        assert stats.fallback_calls == 0

    @pytest.mark.asyncio
    async def test_wrapper_timeout_fallback(self):
        """Test wrapper fallback on timeout."""

        async def slow_primary():
            await asyncio.sleep(0.2)
            return "primary_result"

        config = FallbackConfig(timeout=0.1, triggers=[FallbackTrigger.TIMEOUT])
        provider = StaticValueFallback("timeout_fallback")
        wrapper = AsyncFallbackWrapper("test", provider, config)

        result = await wrapper.execute(slow_primary)
        assert result == "timeout_fallback"

    @pytest.mark.asyncio
    async def test_wrapper_high_latency_fallback(self):
        """Test wrapper fallback on high latency."""

        async def slow_primary():
            await asyncio.sleep(0.15)
            return "primary_result"

        config = FallbackConfig(
            latency_threshold=0.1, triggers=[FallbackTrigger.HIGH_LATENCY]
        )
        provider = StaticValueFallback("latency_fallback")
        wrapper = AsyncFallbackWrapper("test", provider, config)

        result = await wrapper.execute(slow_primary)
        assert result == "latency_fallback"

    @pytest.mark.asyncio
    async def test_wrapper_stats_disabled(self):
        """Test wrapper with stats tracking disabled."""

        async def primary_func():
            return "primary_result"

        config = FallbackConfig(track_fallback_usage=False)
        provider = StaticValueFallback("fallback")
        wrapper = AsyncFallbackWrapper("test", provider, config)

        await wrapper.execute(primary_func)

        # Stats are still updated even when tracking is disabled
        # The tracking flag controls whether stats are used for decisions, not collection
        stats = wrapper.stats
        assert stats.total_calls == 1  # Stats are still collected


class TestFallbackManager:
    """Test FallbackManager class."""

    def test_manager_initialization(self):
        """Test FallbackManager initialization."""
        manager = FallbackManager()
        # Test that manager initializes properly
        assert hasattr(manager, "_fallback_wrappers")
        assert hasattr(manager, "_lock")

    @pytest.mark.asyncio
    async def test_manager_register_wrapper(self):
        """Test registering wrapper with manager."""
        manager = FallbackManager()
        provider = StaticValueFallback("fallback")

        wrapper = await manager.register(
            name="test_func", fallback_provider=provider, config=FallbackConfig()
        )

        assert wrapper.name == "test_func"
        assert isinstance(wrapper, AsyncFallbackWrapper)

    @pytest.mark.asyncio
    async def test_manager_get_wrapper(self):
        """Test getting wrapper from manager."""
        manager = FallbackManager()
        provider = StaticValueFallback("fallback")

        wrapper = await manager.register(
            name="test_func", fallback_provider=provider, config=FallbackConfig()
        )

        retrieved = await manager.get("test_func")
        assert retrieved is wrapper

        # Test non-existent wrapper
        assert await manager.get("non_existent") is None

    @pytest.mark.asyncio
    async def test_manager_remove_wrapper(self):
        """Test removing wrapper from manager."""
        manager = FallbackManager()
        provider = StaticValueFallback("fallback")

        await manager.register(
            name="test_func", fallback_provider=provider, config=FallbackConfig()
        )

        # Verify wrapper exists
        retrieved = await manager.get("test_func")
        assert retrieved is not None

        removed = await manager.unregister("test_func")
        assert removed is True

        # Verify wrapper is removed
        assert await manager.get("test_func") is None

        # Try to remove non-existent wrapper
        removed = await manager.unregister("non_existent")
        assert removed is False

    @pytest.mark.asyncio
    async def test_manager_duplicate_registration(self):
        """Test registering wrapper with duplicate name raises error."""
        manager = FallbackManager()
        provider = StaticValueFallback("fallback")

        # Register first wrapper
        await manager.register("test_func", provider)

        # Try to register with same name
        with pytest.raises(ValueError, match="already registered"):
            await manager.register("test_func", provider)

    @pytest.mark.asyncio
    async def test_manager_bulk_stats(self):
        """Test manager bulk statistics operations."""
        manager = FallbackManager()
        provider = StaticValueFallback("fallback")

        # Register multiple wrappers
        wrapper1 = await manager.register("func1", provider)
        wrapper2 = await manager.register("func2", provider)

        # Execute some operations to generate stats
        async def test_func():
            return "test"

        await wrapper1.execute(test_func)
        await wrapper2.execute(test_func)

        # Test bulk stats
        all_stats = await manager.get_all_stats()
        assert "func1" in all_stats
        assert "func2" in all_stats
        assert all_stats["func1"]["stats"]["total_calls"] == 1
        assert all_stats["func2"]["stats"]["total_calls"] == 1

        # Test bulk reset
        await manager.reset_all_stats()
        all_stats = await manager.get_all_stats()
        assert all_stats["func1"]["stats"]["total_calls"] == 0
        assert all_stats["func2"]["stats"]["total_calls"] == 0

    @pytest.mark.asyncio
    async def test_manager_list_and_cleanup(self):
        """Test manager list and cleanup methods."""
        manager = FallbackManager()
        provider = StaticValueFallback("fallback")

        # Register multiple wrappers
        await manager.register("func1", provider)
        await manager.register("func2", provider)

        # Test list functionality
        wrapper_names = manager.list_fallback_wrappers()
        assert "func1" in wrapper_names
        assert "func2" in wrapper_names
        assert len(wrapper_names) == 2

        # Test cleanup
        await manager.cleanup()

        # After cleanup, no wrappers should remain
        wrapper_names = manager.list_fallback_wrappers()
        assert len(wrapper_names) == 0


class TestFallbackDecorator:
    """Test fallback decorator."""

    @pytest.mark.asyncio
    async def test_fallback_decorator_basic(self):
        """Test basic fallback decorator usage."""
        provider = StaticValueFallback("decorator_fallback")

        @fallback(provider)
        async def decorated_func():
            raise ValueError("Function failed")

        result = await decorated_func()
        assert result == "decorator_fallback"

    @pytest.mark.asyncio
    async def test_fallback_decorator_preserves_success(self):
        """Test fallback decorator doesn't interfere with successful calls."""
        provider = StaticValueFallback("fallback")

        @fallback(provider)
        async def successful_func(value):
            return f"success: {value}"

        result = await successful_func("test")
        assert result == "success: test"


class TestFallbackEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_wrapper_with_no_triggers(self):
        """Test wrapper behavior with no triggers configured."""

        async def failing_primary():
            raise ValueError("Primary failed")

        config = FallbackConfig(triggers=[])  # No triggers, should use defaults
        provider = StaticValueFallback("fallback")
        wrapper = AsyncFallbackWrapper("test", provider, config)

        # Should use fallback because EXCEPTION is a default trigger
        result = await wrapper.execute(failing_primary)
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_wrapper_concurrent_access(self):
        """Test wrapper under concurrent access."""
        call_count = 0

        async def primary_func():
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise ValueError("Even calls fail")
            return f"success_{call_count}"

        config = FallbackConfig(triggers=[FallbackTrigger.EXCEPTION])
        provider = StaticValueFallback("fallback")
        wrapper = AsyncFallbackWrapper("test", provider, config)

        # Run multiple concurrent calls
        tasks = [wrapper.execute(primary_func) for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # Should have mix of successes and fallbacks
        success_count = sum(1 for r in results if r.startswith("success_"))
        fallback_count = sum(1 for r in results if r == "fallback")

        assert success_count + fallback_count == 10
        assert success_count > 0
        assert fallback_count > 0

    @pytest.mark.asyncio
    async def test_wrapper_no_matching_triggers(self):
        """Test wrapper when exception occurs but not in configured triggers."""

        async def failing_primary():
            raise ValueError("Primary failed")

        # Configure only timeout trigger, not exception
        config = FallbackConfig(triggers=[FallbackTrigger.TIMEOUT])
        provider = StaticValueFallback("fallback")
        wrapper = AsyncFallbackWrapper("test", provider, config)

        # Should re-raise exception since EXCEPTION trigger is not configured
        with pytest.raises(ValueError, match="Primary failed"):
            await wrapper.execute(failing_primary)

    @pytest.mark.asyncio
    async def test_wrapper_no_triggers_configured(self):
        """Test wrapper with absolutely no triggers."""

        async def failing_primary():
            raise ValueError("Primary failed")

        # Manually override triggers to be empty (bypass post_init)
        config = FallbackConfig()
        config.triggers = []  # Force empty triggers
        provider = StaticValueFallback("fallback")
        wrapper = AsyncFallbackWrapper("test", provider, config)

        # Should re-raise exception since no triggers are configured
        with pytest.raises(ValueError, match="Primary failed"):
            await wrapper.execute(failing_primary)


class TestFallbackProviderBehaviors:
    """Test specific fallback provider behaviors and edge cases."""

    @pytest.mark.asyncio
    async def test_function_fallback_with_context(self):
        """Test FunctionFallback passes through arguments correctly."""

        # Note: FunctionFallback just calls the function with provided args/kwargs
        # It doesn't automatically pass error/context as named parameters
        async def context_aware_fallback(*args, **kwargs):
            return f"args: {args}, kwargs: {kwargs}"

        provider = FunctionFallback(context_aware_fallback)

        result = await provider.provide_fallback(
            "arg1", error="test_error", context="test_context", kwarg1="value1"
        )

        assert "arg1" in result
        assert "kwarg1" in result

    @pytest.mark.asyncio
    async def test_cache_fallback_key_generation(self):
        """Test CacheFallback key generation with different arguments."""
        cache = {
            "simple": "simple_value",
            "arg1_arg2": "args_value",
            "custom_key": "custom_value",
        }

        def custom_key_generator(*args, **kwargs):
            if kwargs.get("use_custom"):
                return "custom_key"
            return "_".join(str(arg) for arg in args)

        provider = CacheFallback(cache, custom_key_generator, "default")

        # Test simple key
        result = await provider.provide_fallback("simple")
        assert result == "simple_value"

        # Test args-based key
        result = await provider.provide_fallback("arg1", "arg2")
        assert result == "args_value"

        # Test custom key via kwargs
        result = await provider.provide_fallback("ignored", use_custom=True)
        assert result == "custom_value"

        # Test default fallback
        result = await provider.provide_fallback("missing")
        assert result == "default"
