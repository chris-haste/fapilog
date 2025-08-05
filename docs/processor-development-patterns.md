# Processor Development Patterns and Guidelines

This document provides comprehensive guidelines for developing processors in the fapilog library, ensuring consistent async-safe behavior and avoiding race conditions.

## Table of Contents

1. [Overview](#overview)
2. [AsyncProcessorBase Foundation](#asyncprocessorbase-foundation)
3. [Standard Patterns](#standard-patterns)
4. [Testing Framework](#testing-framework)
5. [Performance Guidelines](#performance-guidelines)
6. [Error Handling](#error-handling)
7. [Configuration Management](#configuration-management)
8. [Template Implementation](#template-implementation)
9. [Best Practices](#best-practices)
10. [Common Pitfalls](#common-pitfalls)

## Overview

Processors in fapilog are components that transform, filter, or enrich log events as they flow through the logging pipeline. All processors should follow standardized patterns to ensure:

- **Async Safety**: No race conditions in concurrent environments
- **Performance**: O(1) operations in hot paths
- **Reliability**: Graceful error handling and degradation
- **Testability**: Comprehensive testing support
- **Maintainability**: Clear, consistent patterns

## AsyncProcessorBase Foundation

### Inheritance Pattern

All new processors should inherit from `AsyncProcessorBase` to get access to foundation components:

```python
from fapilog._internal.async_processor_base import AsyncProcessorBase

class MyProcessor(AsyncProcessorBase):
    """My custom processor implementation."""

    def __init__(self, **config):
        super().__init__(**config)
        # Initialize processor-specific state
```

### Foundation Components

`AsyncProcessorBase` provides:

- **ProcessorLockManager**: Centralized async-safe lock management
- **SafeAsyncCache**: Thread-safe cache with LRU eviction
- **Error Handling**: Standardized error handling patterns
- **Metrics Collection**: Built-in metrics and statistics

### Configuration Pattern

```python
def __init__(self, max_events: int = 100, **config):
    # Set attributes before super().__init__() for validate_config()
    self.max_events = max_events

    # Configure cache settings for AsyncProcessorBase
    config.update({
        "cache_max_size": 1000,
        "cache_ttl_seconds": 60,
        "processor_id": "MyProcessor",
    })

    super().__init__(**config)
```

## Standard Patterns

### 1. Process Method Implementation

#### Sync Interface (Backward Compatibility)

```python
def process(self, logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Sync entry point that delegates to async processing."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Async context - schedule async processing
            asyncio.create_task(self.process_async(logger, method_name, event_dict))
            return event_dict  # Return immediately for non-blocking behavior
        else:
            # Sync context - run async version
            return asyncio.run(self.process_async(logger, method_name, event_dict))
    except RuntimeError:
        # No event loop - run sync version
        return asyncio.run(self.process_async(logger, method_name, event_dict))
```

#### Async Interface (Primary Implementation)

```python
async def process_async(self, logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Primary async processing method."""
    try:
        # Step 1: Validate input
        if not self._validate_event(event_dict):
            return event_dict

        # Step 2: Extract processing key
        key = await self._safe_operation(self._extract_key, event_dict)
        if key is None:
            return event_dict

        # Step 3: Process with async-safe patterns
        result = await self._safe_operation(self._process_event, key, event_dict)

        # Step 4: Update metrics atomically
        await self._atomic_update("metrics", self._update_metrics)

        # Return the result directly - None means drop the event
        return result

    except Exception as e:
        # Step 5: Handle errors with standardized patterns
        await self._handle_processor_error(e, {
            "event_dict": event_dict,
            "method_name": method_name,
            "operation": "processing",
        })
        return event_dict
```

### 2. Validation Patterns

```python
def validate_config(self) -> None:
    """Validate processor configuration."""
    if not isinstance(self.max_events, int) or self.max_events <= 0:
        raise ProcessorConfigurationError("max_events must be a positive integer")

    if not isinstance(self.key_field, str) or not self.key_field.strip():
        raise ProcessorConfigurationError("key_field must be a non-empty string")

def _validate_event(self, event_dict: Dict[str, Any]) -> bool:
    """Validate event data."""
    return event_dict is not None and isinstance(event_dict, dict)
```

### 3. Key Extraction Patterns

```python
async def _extract_key(self, event_dict: Dict[str, Any]) -> Optional[str]:
    """Extract processing key from event with error handling."""
    try:
        return str(event_dict.get(self.key_field, "default"))
    except Exception as e:
        logger.warning(f"Failed to extract key from event: {e}")
        return None
```

### 4. Processing Patterns

```python
async def _process_event(self, key: str, event_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Process event with O(1) operations and async-safe patterns."""
    current_time = time.time()

    # Use async-safe cache operations
    cache_key = f"events_{key}"

    # Create a proper async factory function
    async def create_empty_list():
        return []

    events = await self._get_or_create_cached_value(cache_key, create_empty_list)

    # Clean up expired events (O(n) but bounded)
    cutoff_time = current_time - self.window_seconds
    valid_events = [ts for ts in events if ts >= cutoff_time]

    # Check if we should process this event
    if len(valid_events) >= self.max_events:
        return None  # Drop event

    # Add current event timestamp
    valid_events.append(current_time)

    # Update cache atomically
    await self._update_cache_atomic(cache_key, valid_events)

    return event_dict  # Process event
```

### 5. Error Handling Patterns

```python
async def _safe_operation(self, operation: callable, *args, **kwargs) -> Any:
    """Execute operation with standardized error handling."""
    try:
        if asyncio.iscoroutinefunction(operation):
            return await operation(*args, **kwargs)
        else:
            return operation(*args, **kwargs)
    except Exception as e:
        self._error_count += 1
        logger.error(f"Processor operation failed: {e}")
        return None
```

## Testing Framework

### Using ProcessorTestBase

```python
from fapilog._internal.testing.processor_testing import ProcessorTestBase

class TestMyProcessor(ProcessorTestBase):
    """Test class for MyProcessor."""

    def create_processor(self, **config):
        """Create processor instance for testing."""
        return MyProcessor(**config)

    async def test_basic_processing(self, processor):
        """Test basic event processing."""
        event = {"test": "data"}
        result = await processor.process_async(None, "info", event)
        assert result is not None

    async def test_concurrent_access(self, processor):
        """Test concurrent access patterns."""
        await super().test_concurrent_access(processor)

    async def test_error_handling(self, processor):
        """Test error handling scenarios."""
        await super().test_error_handling(processor)
```

### Performance Testing

```python
from fapilog._internal.testing.processor_testing import ProcessorPerformanceTester

async def test_processor_performance():
    processor = MyProcessor()
    tester = ProcessorPerformanceTester(processor)

    # Test throughput
    throughput = await tester.test_throughput(target_ops_per_sec=1000)
    assert throughput > 1000

    # Test latency
    p95_latency = await tester.test_latency_p95(max_p95_ms=10)
    assert p95_latency < 10

    # Test memory stability
    memory_growth = await tester.test_memory_stability(max_growth_percent=10)
    assert memory_growth < 10
```

### Concurrency Testing

```python
from fapilog._internal.testing.processor_testing import ProcessorConcurrencyTester

async def test_processor_concurrency():
    processor = MyProcessor()
    tester = ProcessorConcurrencyTester(processor)

    # Test concurrent shared keys
    await tester.test_concurrent_shared_keys(num_workers=10, num_operations=100)

    # Test concurrent unique keys
    await tester.test_concurrent_unique_keys(num_workers=10, num_operations=100)

    # Test concurrent mixed patterns
    await tester.test_concurrent_mixed_patterns(num_workers=10, num_operations=100)
```

## Performance Guidelines

### 1. O(1) Operations in Hot Paths

Avoid O(n log n) operations in processing methods:

```python
# ❌ Bad: O(n log n) sorting in hot path
sorted_keys = sorted(self._key_access_times.items(), key=lambda x: x[1])

# ✅ Good: O(1) cache operations
events = await self._get_or_create_cached_value(cache_key, lambda: [])
```

### 2. Bounded Memory Usage

Use LRU cache with size limits:

```python
# Configure cache with size limits
config.update({
    "cache_max_size": 1000,
    "cache_ttl_seconds": 60,
})
```

### 3. Background Cleanup

Schedule cleanup operations to avoid blocking hot paths:

```python
async def _schedule_cleanup_if_needed(self, current_time: float):
    """Schedule background cleanup if conditions are met."""
    time_elapsed = (current_time - self._last_cleanup) > self._cleanup_interval
    cache_utilization = self._cache.size() / self.max_cache_size

    if time_elapsed or cache_utilization > 0.8:
        await self._perform_background_cleanup(current_time)
```

## Error Handling

### 1. Graceful Degradation

Always return the original event on error:

```python
async def process_async(self, logger: Any, method_name: str, event_dict: Dict[str, Any]):
    try:
        # Processing logic
        return processed_event
    except Exception as e:
        await self._handle_processor_error(e, context)
        return event_dict  # Return original event
```

### 2. Error Context

Provide rich error context for debugging:

```python
await self._handle_processor_error(e, {
    "event_dict": event_dict,
    "method_name": method_name,
    "operation": "processing",
    "key": key,
})
```

### 3. Error Metrics

Track error rates for monitoring:

```python
self._error_count += 1
logger.error(f"Processor error: {e}")
```

## Configuration Management

### 1. Configuration Validation Pattern

```python
def validate_config(self) -> None:
    """Validate configuration with clear error messages."""
    if not isinstance(self.max_events, int) or self.max_events <= 0:
        raise ProcessorConfigurationError(
            "max_events must be a positive integer"
        )

    if not isinstance(self.window_seconds, int) or self.window_seconds <= 0:
        raise ProcessorConfigurationError(
            "window_seconds must be a positive integer"
        )

    if not isinstance(self.key_field, str) or not self.key_field.strip():
        raise ProcessorConfigurationError(
            "key_field must be a non-empty string"
        )
```

### 2. Configuration in Constructor

```python
def __init__(self, max_events: int = 100, window_seconds: int = 60, key_field: str = "source", **config):
    """Initialize processor with configuration."""
    # Set attributes before super().__init__() for validate_config()
    self.max_events = max_events
    self.window_seconds = window_seconds
    self.key_field = key_field

    # Configure cache settings for AsyncProcessorBase
    config.update({
        "cache_max_size": 1000,
        "cache_ttl_seconds": window_seconds,
        "processor_id": "MyProcessor",
    })

    super().__init__(**config)
    self.validate_config()
```

## Template Implementation

### Complete Template

See `src/fapilog/_internal/templates/processor_template.py` for a complete implementation template that demonstrates all the patterns described in this document.

### Key Template Features

1. **AsyncProcessorBase inheritance**
2. **Standardized error handling**
3. **Performance-optimized operations**
4. **Comprehensive testing support**
5. **Configuration management**
6. **Metrics collection**

## Best Practices

### 1. Always Use AsyncProcessorBase

```python
# ✅ Good: Inherit from AsyncProcessorBase
class MyProcessor(AsyncProcessorBase):
    pass

# ❌ Bad: Inherit directly from Processor
class MyProcessor(Processor):
    pass
```

### 2. Use Async-Safe Operations

```python
# ✅ Good: Use async-safe cache operations
events = await self._get_or_create_cached_value(cache_key, factory)

# ❌ Bad: Direct cache access without locking
events = self._cache.get(cache_key)
```

### 3. Implement Both Sync and Async Interfaces

```python
# Sync interface for backward compatibility
def process(self, logger, method_name, event_dict):
    # Delegate to async version
    pass

# Async interface for primary implementation
async def process_async(self, logger, method_name, event_dict):
    # Main processing logic
    pass
```

### 4. Provide Comprehensive Metrics

```python
def get_metrics(self) -> Dict[str, Any]:
    """Get processor metrics."""
    base_metrics = super().get_metrics() if hasattr(super(), 'get_metrics') else {}
    return {
        **base_metrics,
        "processed_count": self._processed_count,
        "dropped_count": self._dropped_count,
        "error_count": self._error_count,
        "max_events": self.max_events,
        "window_seconds": self.window_seconds,
        "key_field": self.key_field,
    }
```

### 5. Write Comprehensive Tests

```python
class TestMyProcessor(ProcessorTestBase):
    def create_processor(self, **config):
        return MyProcessor(**config)

    async def test_basic_processing(self, processor):
        # Test basic functionality
        pass

    async def test_concurrent_access(self, processor):
        # Test concurrency
        pass

    async def test_error_handling(self, processor):
        # Test error scenarios
        pass
```

## Common Pitfalls

### 1. Race Conditions

```python
# ❌ Bad: Direct attribute access without locking
self._events[key].append(timestamp)

# ✅ Good: Use async-safe operations
await self._update_cache_atomic(cache_key, updated_events)
```

### 2. Memory Leaks

```python
# ❌ Bad: Unbounded growth
self._events[key].append(timestamp)

# ✅ Good: Bounded cache with cleanup
await self._update_cache_atomic(cache_key, bounded_events)
```

### 3. Blocking Operations

```python
# ❌ Bad: Blocking operations in async context
time.sleep(1)

# ✅ Good: Non-blocking async operations
await asyncio.sleep(1)
```

### 4. Inconsistent Error Handling

```python
# ❌ Bad: Inconsistent error handling
try:
    result = process_event(event)
except Exception:
    pass  # Silent failure

# ✅ Good: Standardized error handling
try:
    result = await self._safe_operation(process_event, event)
except Exception as e:
    await self._handle_processor_error(e, context)
    return event_dict  # Graceful degradation
```

## Conclusion

Following these patterns ensures that all processors in fapilog are:

- **Async-safe** with no race conditions
- **Performance-optimized** with O(1) operations
- **Reliable** with graceful error handling
- **Testable** with comprehensive testing support
- **Maintainable** with clear, consistent patterns

Use the provided template and testing framework to implement new processors that follow these guidelines.
