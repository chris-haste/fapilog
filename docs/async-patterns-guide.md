# Async Patterns Guide for SmartCache

## Overview

This guide provides comprehensive patterns and best practices for working with AsyncSmartCache and async enrichers in Fapilog. Understanding these patterns is essential for building high-performance, race-condition-free logging systems.

## Core Async Patterns

### 1. Basic Async Cache Operations

#### Simple Cache Usage

```python
from fapilog.enrichers import AsyncSmartCache
from datetime import timedelta

# Initialize cache with appropriate retry interval
cache = AsyncSmartCache(retry_interval=timedelta(minutes=5))

async def get_user_data(user_id: str):
    """Get user data with caching."""
    async def fetch_user():
        # Simulate API call
        await asyncio.sleep(0.1)
        return {"id": user_id, "name": f"User_{user_id}"}

    return await cache.get_or_compute(f"user_{user_id}", fetch_user)
```

#### Parameterized Cache Keys

```python
async def get_configuration(env: str, service: str):
    """Get configuration with composite cache key."""
    async def load_config():
        # Load configuration from external source
        config = await load_service_config(env, service)
        return config

    cache_key = f"config_{env}_{service}"
    return await cache.get_or_compute(cache_key, load_config)
```

### 2. Error Handling Patterns

#### Graceful Error Handling

```python
async def robust_cache_operation(key: str):
    """Handle both fresh and cached errors gracefully."""
    try:
        result = await cache.get_or_compute(key, expensive_computation)
        return result
    except RuntimeError as e:
        if "Cached error" in str(e):
            # Handle cached error - maybe use fallback
            logger.warning(f"Using cached error for {key}, using fallback")
            return get_fallback_value(key)
        else:
            # Re-raise unexpected RuntimeErrors
            raise
    except ConnectionError:
        # Handle fresh connection errors
        logger.error(f"Connection failed for {key}")
        return None
    except Exception as e:
        # Handle other computation errors
        logger.error(f"Computation failed for {key}: {e}")
        return None
```

#### Retry with Exponential Backoff

```python
import asyncio
from typing import Optional

async def cache_with_retry(
    key: str,
    compute_func,
    max_retries: int = 3,
    base_delay: float = 0.1
) -> Optional[any]:
    """Cache operation with exponential backoff retry."""

    for attempt in range(max_retries + 1):
        try:
            return await cache.get_or_compute(key, compute_func)
        except RuntimeError as e:
            if "Cached error" in str(e) and attempt < max_retries:
                # Wait before retry with exponential backoff
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
                continue
            raise
        except Exception as e:
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
                continue
            raise

    return None
```

### 3. Concurrent Operation Patterns

#### Parallel Cache Operations

```python
async def fetch_multiple_resources(resource_ids: List[str]):
    """Fetch multiple resources concurrently with caching."""

    async def fetch_resource(resource_id: str):
        async def load_resource():
            # Simulate resource loading
            await asyncio.sleep(0.05)
            return f"resource_data_{resource_id}"

        return await cache.get_or_compute(f"resource_{resource_id}", load_resource)

    # Launch all operations concurrently
    tasks = [fetch_resource(rid) for rid in resource_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results, handling any exceptions
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.warning(f"Failed to fetch resource {resource_ids[i]}: {result}")
            processed_results.append(None)
        else:
            processed_results.append(result)

    return processed_results
```

#### Rate-Limited Cache Operations

```python
import asyncio
from asyncio import Semaphore

class RateLimitedCache:
    """Cache wrapper with rate limiting."""

    def __init__(self, cache: AsyncSmartCache, max_concurrent: int = 10):
        self.cache = cache
        self.semaphore = Semaphore(max_concurrent)

    async def get_or_compute(self, key: str, compute_func):
        """Rate-limited cache operation."""
        async with self.semaphore:
            return await self.cache.get_or_compute(key, compute_func)

# Usage
rate_limited_cache = RateLimitedCache(cache, max_concurrent=5)

async def controlled_fetch(item_id: str):
    """Fetch with concurrency control."""
    return await rate_limited_cache.get_or_compute(
        f"item_{item_id}",
        lambda: fetch_external_data(item_id)
    )
```

## Enricher Patterns

### 1. Simple Async Enricher

```python
from fapilog.enrichers import register_enricher, AsyncSmartCache

_enricher_cache = AsyncSmartCache(retry_interval=timedelta(minutes=10))

async def system_info_enricher(logger, method_name, event_dict):
    """Add system information to log events."""

    async def get_system_info():
        import psutil
        return {
            "hostname": socket.gethostname(),
            "pid": os.getpid(),
            "memory_mb": psutil.virtual_memory().used // 1024 // 1024,
            "cpu_percent": psutil.cpu_percent()
        }

    if "system_info" not in event_dict:
        system_info = await _enricher_cache.get_or_compute(
            "system_info", get_system_info
        )
        event_dict["system_info"] = system_info

    return event_dict

# Register the enricher
register_enricher(system_info_enricher)
```

### 2. Context-Aware Enricher

```python
async def request_context_enricher(logger, method_name, event_dict):
    """Enrich with request context information."""

    # Get request context (if available)
    request = get_current_request()  # Your context management
    if not request:
        return event_dict

    async def get_user_details(user_id: str):
        # Fetch user details from database/API
        return await fetch_user_from_api(user_id)

    # Add request ID
    if hasattr(request, 'id'):
        event_dict["request_id"] = request.id

    # Add user details if user_id is available
    if hasattr(request, 'user_id') and request.user_id:
        try:
            user_details = await _enricher_cache.get_or_compute(
                f"user_{request.user_id}",
                lambda: get_user_details(request.user_id)
            )
            event_dict["user"] = {
                "id": user_details["id"],
                "role": user_details.get("role", "unknown")
            }
        except Exception as e:
            # Don't let enricher failures break logging
            event_dict["user_fetch_error"] = str(e)

    return event_dict
```

### 3. Performance-Optimized Enricher

```python
from typing import Dict, Any
import time

async def performance_enricher(logger, method_name, event_dict):
    """Add performance metrics with efficient caching."""

    # Cache expensive operations with short TTL
    current_minute = int(time.time() // 60)  # Cache per minute

    async def get_performance_metrics():
        return {
            "timestamp": time.time(),
            "process_stats": get_process_stats(),
            "system_load": get_system_load()
        }

    # Use time-based cache key for automatic expiration
    cache_key = f"perf_metrics_{current_minute}"

    try:
        metrics = await _enricher_cache.get_or_compute(
            cache_key, get_performance_metrics
        )
        event_dict["performance"] = metrics
    except Exception as e:
        # Fallback to minimal metrics on error
        event_dict["performance"] = {
            "error": str(e),
            "timestamp": time.time()
        }

    return event_dict
```

### 4. Multi-Level Cache Pattern

```python
class MultiLevelEnricher:
    """Enricher with multiple cache levels for different data types."""

    def __init__(self):
        # Fast cache for frequently accessed data
        self.fast_cache = AsyncSmartCache(retry_interval=timedelta(minutes=1))

        # Slow cache for expensive operations
        self.slow_cache = AsyncSmartCache(retry_interval=timedelta(minutes=30))

        # Error cache for failed operations
        self.error_cache = AsyncSmartCache(retry_interval=timedelta(minutes=5))

    async def __call__(self, logger, method_name, event_dict):
        """Multi-level enrichment."""

        # Fast enrichment (hostname, PID, etc.)
        await self._add_fast_data(event_dict)

        # Slow enrichment (external APIs, complex calculations)
        await self._add_slow_data(event_dict)

        return event_dict

    async def _add_fast_data(self, event_dict: Dict[str, Any]):
        """Add quickly accessible data."""
        async def get_process_info():
            return {
                "hostname": socket.gethostname(),
                "pid": os.getpid(),
                "thread_id": threading.get_ident()
            }

        process_info = await self.fast_cache.get_or_compute(
            "process_info", get_process_info
        )
        event_dict.update(process_info)

    async def _add_slow_data(self, event_dict: Dict[str, Any]):
        """Add data requiring expensive operations."""
        async def get_external_config():
            # Simulate slow external call
            await asyncio.sleep(0.1)
            return {"feature_flags": ["flag1", "flag2"]}

        try:
            config = await self.slow_cache.get_or_compute(
                "external_config", get_external_config
            )
            event_dict["config"] = config
        except Exception as e:
            # Use error cache to avoid repeated failures
            error_info = await self.error_cache.get_or_compute(
                "config_error",
                lambda: {"error": str(e), "timestamp": time.time()}
            )
            event_dict["config_error"] = error_info
```

## Advanced Patterns

### 1. Cache Warming Pattern

```python
class CacheWarmer:
    """Proactively warm cache with essential data."""

    def __init__(self, cache: AsyncSmartCache):
        self.cache = cache
        self.warming_tasks = set()

    async def warm_cache(self):
        """Warm cache with essential data."""
        essential_keys = [
            ("hostname", socket.gethostname),
            ("pid", os.getpid),
            ("start_time", time.time),
        ]

        warming_tasks = [
            self.cache.get_or_compute(key, func)
            for key, func in essential_keys
        ]

        results = await asyncio.gather(*warming_tasks, return_exceptions=True)

        # Log warming results
        for i, result in enumerate(results):
            key = essential_keys[i][0]
            if isinstance(result, Exception):
                logger.warning(f"Failed to warm cache for {key}: {result}")
            else:
                logger.debug(f"Warmed cache for {key}")

    async def start_background_warming(self):
        """Start background cache warming."""
        async def warming_loop():
            while True:
                try:
                    await self.warm_cache()
                    await asyncio.sleep(300)  # Warm every 5 minutes
                except Exception as e:
                    logger.error(f"Cache warming failed: {e}")
                    await asyncio.sleep(60)  # Retry after 1 minute

        # Start warming task
        task = asyncio.create_task(warming_loop())
        self.warming_tasks.add(task)
        return task

# Usage
warmer = CacheWarmer(cache)
await warmer.start_background_warming()
```

### 2. Cache Invalidation Pattern

```python
class InvalidatableCache:
    """Cache with selective invalidation capabilities."""

    def __init__(self, base_cache: AsyncSmartCache):
        self.cache = base_cache
        self.key_patterns = {}

    async def get_or_compute(self, key: str, compute_func, pattern: str = None):
        """Cache with pattern tracking for invalidation."""
        if pattern:
            if pattern not in self.key_patterns:
                self.key_patterns[pattern] = set()
            self.key_patterns[pattern].add(key)

        return await self.cache.get_or_compute(key, compute_func)

    async def invalidate_pattern(self, pattern: str):
        """Invalidate all keys matching a pattern."""
        if pattern in self.key_patterns:
            keys_to_invalidate = self.key_patterns[pattern].copy()

            for key in keys_to_invalidate:
                # Remove from cache (implementation depends on cache internals)
                if hasattr(self.cache, '_cache') and key in self.cache._cache:
                    async with self.cache._lock:
                        del self.cache._cache[key]

            # Clear pattern tracking
            self.key_patterns[pattern].clear()

            logger.info(f"Invalidated {len(keys_to_invalidate)} keys for pattern: {pattern}")

# Usage
invalidatable_cache = InvalidatableCache(cache)

async def user_enricher(logger, method_name, event_dict):
    user_id = event_dict.get("user_id")
    if user_id:
        user_data = await invalidatable_cache.get_or_compute(
            f"user_{user_id}",
            lambda: fetch_user_data(user_id),
            pattern="user_data"  # Track for invalidation
        )
        event_dict["user"] = user_data
    return event_dict

# Invalidate user data when needed
await invalidatable_cache.invalidate_pattern("user_data")
```

### 3. Circuit Breaker Pattern

```python
import time
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if service recovered

class CircuitBreakerCache:
    """Cache with circuit breaker for external dependencies."""

    def __init__(
        self,
        cache: AsyncSmartCache,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        expected_exception=Exception
    ):
        self.cache = cache
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED

    async def get_or_compute(self, key: str, compute_func, fallback_func=None):
        """Cache with circuit breaker protection."""

        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                # Circuit is open, use fallback
                if fallback_func:
                    return await fallback_func()
                raise Exception("Circuit breaker is OPEN")

        try:
            result = await self.cache.get_or_compute(key, compute_func)
            self._on_success()
            return result

        except self.expected_exception as e:
            self._on_failure()

            if fallback_func:
                return await fallback_func()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        return (
            self.last_failure_time is not None and
            time.time() - self.last_failure_time >= self.timeout
        )

    def _on_success(self):
        """Handle successful operation."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def _on_failure(self):
        """Handle failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

# Usage
circuit_cache = CircuitBreakerCache(
    cache,
    failure_threshold=3,
    timeout=30.0,
    expected_exception=ConnectionError
)

async def resilient_enricher(logger, method_name, event_dict):
    """Enricher with circuit breaker protection."""

    async def fetch_external_data():
        # This might fail
        return await call_external_api()

    async def fallback_data():
        return {"status": "fallback", "timestamp": time.time()}

    try:
        external_data = await circuit_cache.get_or_compute(
            "external_data",
            fetch_external_data,
            fallback_func=fallback_data
        )
        event_dict["external"] = external_data
    except Exception as e:
        event_dict["external_error"] = str(e)

    return event_dict
```

## Performance Best Practices

### 1. Cache Key Design

```python
# Good: Specific, hierarchical keys
cache_key = f"user_profile_{user_id}_{version}"
cache_key = f"config_{environment}_{service_name}_{config_version}"

# Bad: Generic keys that could collide
cache_key = "user_data"
cache_key = "config"

# Good: Include relevant context
cache_key = f"metrics_{metric_type}_{time_bucket}_{aggregation_level}"
```

### 2. Async Function Optimization

```python
# Good: Dedicated async functions for cache operations
async def get_user_permissions(user_id: str) -> List[str]:
    """Dedicated async function for user permissions."""
    async def fetch_permissions():
        # Use async HTTP client
        async with httpx.AsyncClient() as client:
            response = await client.get(f"/api/users/{user_id}/permissions")
            return response.json()["permissions"]

    return await cache.get_or_compute(f"permissions_{user_id}", fetch_permissions)

# Bad: Mixing sync and async inappropriately
def mixed_function(user_id: str):
    # Don't do this - mixing sync and async incorrectly
    return asyncio.run(cache.get_or_compute(f"user_{user_id}", sync_function))
```

### 3. Error Handling Strategy

```python
async def robust_enricher_pattern(logger, method_name, event_dict):
    """Template for robust enricher with proper error handling."""

    enrichment_tasks = []

    # Add multiple enrichment tasks
    enrichment_tasks.append(add_system_info(event_dict))
    enrichment_tasks.append(add_user_context(event_dict))
    enrichment_tasks.append(add_performance_metrics(event_dict))

    # Execute all enrichments concurrently
    results = await asyncio.gather(*enrichment_tasks, return_exceptions=True)

    # Handle results
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            task_name = enrichment_tasks[i].__name__
            logger.warning(f"Enrichment {task_name} failed: {result}")
            event_dict[f"{task_name}_error"] = str(result)

    return event_dict
```

## Testing Patterns

### 1. Testing Async Enrichers

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_async_enricher():
    """Test async enricher with proper mocking."""

    # Mock the cache
    mock_cache = AsyncMock()
    mock_cache.get_or_compute.return_value = {"hostname": "test-host"}

    with patch("my_module._enricher_cache", mock_cache):
        result = await system_info_enricher(None, None, {})

        assert "system_info" in result
        assert result["system_info"]["hostname"] == "test-host"
        mock_cache.get_or_compute.assert_called_once()

@pytest.mark.asyncio
async def test_enricher_error_handling():
    """Test enricher handles cache errors gracefully."""

    mock_cache = AsyncMock()
    mock_cache.get_or_compute.side_effect = ConnectionError("Network failed")

    with patch("my_module._enricher_cache", mock_cache):
        # Should not raise exception
        result = await system_info_enricher(None, None, {})

        # Should have error information
        assert "system_info_error" in result or "system_info" not in result
```

### 2. Performance Testing

```python
import time
import asyncio

@pytest.mark.asyncio
async def test_cache_performance():
    """Test cache performance under load."""

    cache = AsyncSmartCache()
    call_count = 0

    async def expensive_operation():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)  # Simulate work
        return f"result_{call_count}"

    # Launch many concurrent operations
    start_time = time.time()
    tasks = [
        cache.get_or_compute("test_key", expensive_operation)
        for _ in range(1000)
    ]

    results = await asyncio.gather(*tasks)
    end_time = time.time()

    # Verify performance
    assert len(set(results)) == 1  # All same result (cached)
    assert call_count == 1  # Only called once
    assert end_time - start_time < 1.0  # Completed quickly
```

## Monitoring and Debugging

### 1. Cache Monitoring

```python
async def monitor_cache_performance(cache: AsyncSmartCache):
    """Monitor cache performance metrics."""

    while True:
        try:
            stats = await cache.get_cache_stats()

            # Log metrics
            logger.info(
                "Cache performance",
                extra={
                    "total_entries": stats["total_entries"],
                    "success_entries": stats["success_entries"],
                    "error_entries": stats["error_entries"],
                    "hit_rate": stats["cache_hit_rate"]
                }
            )

            await asyncio.sleep(60)  # Monitor every minute

        except Exception as e:
            logger.error(f"Cache monitoring failed: {e}")
            await asyncio.sleep(60)
```

### 2. Debug Logging

```python
import logging

# Enable debug logging for cache operations
logging.getLogger("fapilog.enrichers").setLevel(logging.DEBUG)

async def debug_enricher(logger, method_name, event_dict):
    """Enricher with debug logging."""

    start_time = time.time()

    try:
        result = await cache.get_or_compute("debug_key", compute_function)

        duration = time.time() - start_time
        logger.debug(f"Cache operation completed in {duration:.3f}s")

        return event_dict

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Cache operation failed after {duration:.3f}s: {e}")
        raise
```

This guide provides the foundation for building robust, high-performance async applications with SmartCache. Remember to always test your async patterns thoroughly and monitor performance in production environments.
