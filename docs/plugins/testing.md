# Plugin Testing

fapilog ships testing utilities for every plugin type so you can validate behavior quickly and catch contract drift.

## Quick Start

```python
import pytest
from fapilog.testing import MockSink, validate_sink


@pytest.mark.asyncio
async def test_my_sink_contract() -> None:
    sink = MockSink()
    result = validate_sink(sink)
    result.raise_if_invalid()
```

## Mock Plugins

- **MockSink**: captures written events, tracks lifecycle calls, optional latency/failure injection (`MockSinkConfig`).
- **MockEnricher**: returns configured fields and tracks calls (`MockEnricherConfig`).
- **MockRedactor**: masks configured fields with deep copy handling (`MockRedactorConfig`).
- **MockProcessor**: echoes bytes, tracking processed views.
- **MockFilter**: drops events by level or probability with optional failure injection (`MockFilterConfig`).

Example filter usage:

```python
from fapilog.testing import MockFilter, MockFilterConfig

filter_plugin = MockFilter(
    MockFilterConfig(drop_levels=["DEBUG", "TRACE"], drop_rate=0.1)
)

await filter_plugin.start()
event = {"level": "INFO", "message": "kept"}
assert await filter_plugin.filter(event) == event
await filter_plugin.stop()
```

## Validators

Use validators to ensure plugins satisfy protocol contracts:

- `validate_sink`, `validate_enricher`, `validate_redactor`, `validate_processor`, `validate_filter`
- `validate_plugin_lifecycle` to exercise `start()`/`stop()` without changing behavior.

```python
from fapilog.testing import validate_filter

class MyFilter:
    name = "my-filter"
    async def start(self): ...
    async def stop(self): ...
    async def filter(self, event: dict): ...
    async def health_check(self): return True

validate_filter(MyFilter()).raise_if_invalid()
```

## pytest Fixtures

Load fixtures via pytest's plugin mechanism:

```python
# conftest.py
pytest_plugins = ("fapilog.testing.fixtures",)
```

Available fixtures: `mock_sink`, `mock_enricher`, `mock_redactor`, `mock_processor`, `mock_filter`, and `started_mock_sink` (async, cleans up automatically).

Assertion helpers raise `ProtocolViolationError` when contracts break:

- `assert_valid_sink`, `assert_valid_enricher`, `assert_valid_redactor`, `assert_valid_processor`, `assert_valid_filter`

## Benchmarks

Measure plugin performance with lightweight benchmarks:

- `benchmark_async` for generic async call benchmarking
- `benchmark_sink`, `benchmark_enricher`, `benchmark_filter` helpers that manage lifecycle
- `BenchmarkResult` provides `ops_per_second`, latency metrics, and a readable `__str__`

```python
from fapilog.testing import MockSink
from fapilog.testing import benchmark_sink

result = await benchmark_sink(MockSink(), iterations=200, warmup=10)
print(result)  # sink:mock: 50000 ops/s, avg=0.020ms
```

## CI/CD Integration

- Run validators alongside unit tests to catch contract regressions early.
- Use fixtures for smoke tests that exercise pipelines without hitting external systems.
- Add a lightweight benchmark job to watch for performance regressions in custom plugins.
- Gate merges on `ProtocolViolationError`-free results to keep plugins compatible across releases.
