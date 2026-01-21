# Testing Plugins

fapilog provides comprehensive testing utilities to help you develop and validate custom plugins.

## Installation

The testing utilities are included in the main `fapilog` package:

```python
from fapilog.testing import (
    # Mock plugins
    MockSink,
    MockEnricher,
    MockRedactor,
    MockProcessor,
    # Validators
    validate_sink,
    validate_enricher,
    validate_redactor,
    validate_processor,
    validate_plugin_lifecycle,
    # Factories
    create_log_event,
    create_batch_events,
    create_sensitive_event,
)
```

## Mock Plugins

### MockSink

A configurable mock sink that captures written events for inspection:

```python
from fapilog.testing import MockSink, MockSinkConfig

# Basic usage
sink = MockSink()
await sink.start()
await sink.write({"level": "INFO", "message": "test"})

assert len(sink.events) == 1
assert sink.events[0]["message"] == "test"

# With failure simulation
config = MockSinkConfig(
    fail_after=5,  # Fail after 5 writes
    fail_with=IOError("connection lost"),
    latency_seconds=0.1,  # Simulate network latency
)
sink = MockSink(config)

# Assertion helpers
sink.assert_event_count(1)
sink.assert_event_contains(0, level="INFO", message="test")

# Reset for reuse
sink.reset()
```

### MockEnricher

A mock enricher that adds configurable fields:

```python
from fapilog.testing import MockEnricher, MockEnricherConfig

config = MockEnricherConfig(
    fields_to_add={"service": "test", "version": "1.0.0"},
    latency_seconds=0.05,
)
enricher = MockEnricher(config)

result = await enricher.enrich({"message": "hello"})
assert result == {"service": "test", "version": "1.0.0"}
```

### MockRedactor

A mock redactor that masks specified fields:

```python
from fapilog.testing import MockRedactor, MockRedactorConfig

config = MockRedactorConfig(
    fields_to_mask=["user.password", "auth.token"],
    mask_string="***REDACTED***",
)
redactor = MockRedactor(config)

event = {"user": {"name": "alice", "password": "secret"}}
result = await redactor.redact(event)
assert result["user"]["password"] == "***REDACTED***"
```

### MockProcessor

A mock processor for testing memoryview operations:

```python
from fapilog.testing import MockProcessor

processor = MockProcessor()
view = memoryview(b'{"message": "test"}')
result = await processor.process(view)

assert processor.call_count == 1
```

## Protocol Validators

Use validators to verify your plugins implement protocols correctly:

```python
from fapilog.testing import validate_sink, validate_enricher

class MyCustomSink:
    name = "my-sink"
    
    async def start(self) -> None:
        pass
    
    async def stop(self) -> None:
        pass
    
    async def write(self, entry: dict) -> None:
        print(entry)


def test_my_sink_protocol():
    sink = MyCustomSink()
    result = validate_sink(sink)
    
    assert result.valid, f"Validation failed: {result.errors}"
    assert not result.warnings
```

### What Validators Check

Each validator checks:

1. **`name` attribute** - Must be present and be a string
2. **Required methods** - Must exist and be async
3. **Method signatures** - Must accept correct parameters

### validate_plugin_lifecycle

Test that lifecycle methods work correctly:

```python
import pytest
from fapilog.testing import validate_plugin_lifecycle

@pytest.mark.asyncio
async def test_my_sink_lifecycle():
    sink = MyCustomSink()
    result = await validate_plugin_lifecycle(sink)
    
    assert result.valid
    # Checks:
    # - start() doesn't raise
    # - stop() doesn't raise
    # - stop() is idempotent (can be called twice)
```

## Test Data Factories

Generate realistic test data for your tests:

```python
from fapilog.testing import (
    create_log_event,
    create_batch_events,
    create_sensitive_event,
)

# Single event with defaults
event = create_log_event()
# {"level": "INFO", "message": "Test message 1234", ...}

# With custom values
event = create_log_event(
    level="ERROR",
    message="Something went wrong",
    user_id="user-123",
)

# Batch of events
events = create_batch_events(count=100, level="DEBUG")

# Event with sensitive data (for redaction testing)
sensitive = create_sensitive_event()
# Contains: password, ssn, card_number, api_key, etc.
```

## Testing Patterns

### Testing a Custom Sink

```python
import pytest
from fapilog.testing import validate_sink, create_log_event


class MyDatabaseSink:
    name = "my-database"
    
    def __init__(self, connection_string: str):
        self._conn_str = connection_string
        self._client = None
    
    async def start(self) -> None:
        self._client = await connect(self._conn_str)
    
    async def stop(self) -> None:
        if self._client:
            await self._client.close()
    
    async def write(self, entry: dict) -> None:
        await self._client.insert(entry)
    
    async def health_check(self) -> bool:
        return self._client is not None and self._client.is_connected()


def test_protocol_compliance():
    sink = MyDatabaseSink("sqlite:///:memory:")
    result = validate_sink(sink)
    result.raise_if_invalid()


@pytest.mark.asyncio
async def test_write_events():
    sink = MyDatabaseSink("sqlite:///:memory:")
    await sink.start()
    
    event = create_log_event(level="INFO", message="test")
    await sink.write(event)
    
    # Verify event was written
    # ...
    
    await sink.stop()
```

### Testing a Custom Enricher

```python
import time
import pytest
from fapilog.testing import validate_enricher, create_log_event


class MyEnricher:
    name = "my-enricher"
    
    async def start(self) -> None:
        pass
    
    async def stop(self) -> None:
        pass
    
    async def enrich(self, event: dict) -> dict:
        return {"enriched_at": time.time()}


def test_protocol_compliance():
    enricher = MyEnricher()
    result = validate_enricher(enricher)
    assert result.valid


@pytest.mark.asyncio
async def test_enrichment():
    enricher = MyEnricher()
    event = create_log_event()
    
    additions = await enricher.enrich(event)
    
    assert "enriched_at" in additions
    assert isinstance(additions["enriched_at"], float)
```

### Testing Redaction

```python
import pytest
from fapilog.testing import create_sensitive_event


@pytest.mark.asyncio
async def test_redacts_sensitive_fields():
    redactor = MyRedactor(fields=["password", "ssn"])
    event = create_sensitive_event()
    
    result = await redactor.redact(event)
    
    assert result["user"]["password"] != "supersecret123"
    assert result["user"]["ssn"] != "123-45-6789"
```

## Test Isolation with Logger Caching

Since fapilog caches logger instances by name, tests need isolation to avoid shared state. Two approaches:

### Option 1: Use `reuse=False` (Recommended)

Create independent logger instances per test:

```python
@pytest.mark.asyncio
async def test_my_feature():
    # reuse=False creates a fresh instance not added to cache
    logger = await get_async_logger("test", reuse=False)

    await logger.info("test message")

    # Clean up when done
    await logger.drain()
```

### Option 2: Clear Cache in Fixtures

Clear the cache before/after tests:

```python
import pytest
from fapilog import clear_logger_cache

@pytest.fixture(autouse=True)
async def isolate_logger_cache():
    await clear_logger_cache()
    yield
    await clear_logger_cache()
```

The fapilog test suite uses an autouse fixture in `conftest.py` that clears the cache between tests.

## Best Practices

1. **Always validate protocol compliance** before testing behavior
2. **Use mock plugins** to test integration without external dependencies
3. **Use factories** for consistent, realistic test data
4. **Test lifecycle methods** to ensure proper resource management
5. **Test error handling** by configuring mocks to fail
6. **Test idempotency** - call `stop()` twice to verify it doesn't break
7. **Use `reuse=False`** when creating loggers in tests that need isolation

## Migration Notes

As of fapilog 0.4.0, all plugin protocols require a `name` attribute:

```python
# Before (may fail validation)
class MySink:
    async def write(self, entry: dict) -> None:
        ...

# After (correct)
class MySink:
    name = "my-sink"  # Required!
    
    async def write(self, entry: dict) -> None:
        ...
```

If you have existing plugins without `name`, add it as a class attribute with a unique identifier for your plugin.

