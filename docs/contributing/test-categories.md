---
orphan: true
---

# Test Categories

Tests are categorized by risk level and type for selective execution.

## Risk Markers

| Marker | Description | Required for |
| --- | --- | --- |
| `@pytest.mark.critical` | Core functionality that must never break | Logger, worker, queue |
| `@pytest.mark.security` | Security-critical paths | Redaction, auth |
| `@pytest.mark.standard` | Default for typical unit tests (optional) | Everything else |

## Type Markers

| Marker | Description |
| --- | --- |
| `@pytest.mark.integration` | Requires external dependencies |
| `@pytest.mark.slow` | Takes >1 second |
| `@pytest.mark.flaky` | Known intermittent failures (time-boxed) |
| `@pytest.mark.postgres` | Requires PostgreSQL |
| `@pytest.mark.property` | Property-based (Hypothesis) |

Unmarked tests are treated as `standard`.

## Flaky Policy

- `@pytest.mark.flaky` requires an issue link and expiry date in the test docstring.
- `flaky` is never allowed on `critical` or `security`.
- Flaky tests run in a quarantined allow-fail job or as `xfail`.

## Running Subsets

```bash
# Only critical tests (fast feedback)
pytest -m critical

# Security tests
pytest -m security

# Skip slow tests
pytest -m "not slow"

# Skip integration tests
pytest -m "not integration"

# Unit tests only
pytest tests/unit/ -m "not slow"

# Skip flaky tests
pytest -m "not flaky"
```

## Verifying Markers

```bash
# Report unknown markers and unmarked tests
python scripts/verify_test_markers.py tests/

# Strict mode (fails on unmarked tests)
python scripts/verify_test_markers.py --strict tests/
```

## Adding Markers

Prefer module-level `pytestmark` or class decorators to reduce per-test overhead. Unmarked tests
default to `standard`, so only critical/security/integration/slow/flaky need
explicit markers.

Module-level example:

```python
# tests/integration/test_postgres.py
pytestmark = [pytest.mark.integration, pytest.mark.security]
```

Function-level example:

```python
@pytest.mark.security
@pytest.mark.integration
async def test_redaction_reaches_sink():
    ...
```

## CI Timeout Multipliers

Tests with timing-sensitive operations (sleep-based waits, recovery timeouts) can fail on slow CI runners. Use the `get_test_timeout()` helper to scale timeouts appropriately:

```python
from conftest import get_test_timeout

# Timeout configuration
config = SinkCircuitBreakerConfig(
    failure_threshold=1,
    recovery_timeout_seconds=get_test_timeout(0.05),  # 50ms locally, 150ms in CI
)

# Sleep-based waits
time.sleep(get_test_timeout(0.06))  # 60ms locally, 180ms in CI
```

### How It Works

The `CI_TIMEOUT_MULTIPLIER` environment variable scales all timeouts:

| Environment | Multiplier | Effect |
| --- | --- | --- |
| Local (default) | 1.0 | No scaling |
| CI | 3.0 | 3x longer timeouts |
| Max allowed | 5.0 | Capped to prevent hangs |

### When to Use

Use `get_test_timeout()` for:
- Recovery timeout configurations
- `time.sleep()` calls waiting for timeouts
- `asyncio.wait_for()` timeout values
- Any timing where CI slowness could cause flakiness

Don't use for:
- Performance assertions (use `@pytest.mark.skipif(CI)` instead)
- Fixed delays that don't depend on system speed
- Production code (test-only helper)

### Configuration

CI sets the multiplier automatically via environment variable:

```yaml
# .github/workflows/ci.yml
env:
  CI_TIMEOUT_MULTIPLIER: "3"
```

```ini
# tox.ini
setenv =
    CI_TIMEOUT_MULTIPLIER = 3
```
