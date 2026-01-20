# Plugin Error Handling

Guidance for containing errors in sinks, enrichers, redactors, and processors without breaking the logging pipeline.

## Core Principle: Contain Errors (With Sink Exception)

Most plugins must not leak exceptions into the core pipeline from `enrich()`, `redact()`, or `process()`. Handle failures locally, emit diagnostics, and return a safe fallback so other plugins keep running.

**Sinks are different**: As of v0.4, sinks should **signal failures** to enable fallback and circuit breaker behavior. Raise `SinkWriteError` or return `False` from `write()`. The core catches these signals safely—no exceptions propagate to user code.

## When Raising Is Acceptable

- `__init__`: Reject invalid configuration or missing dependencies.
- `start()`: Fail fast if required resources cannot be acquired (or contain and mark unhealthy).
- `write()` (sinks only): Raise `SinkWriteError` or return `False` to signal failure. The core triggers fallback and increments circuit breaker counters.
- All other methods (enrichers, redactors, processors): contain errors; do not re-raise into the pipeline.

## Diagnostics API (rate-limited)

Use `fapilog.core.diagnostics.warn` for structured, rate-limited warnings:

```python
from fapilog.core.diagnostics import warn

warn("my-sink", "failed to send log", error=str(exc), attempt=3)

# Optional rate limit grouping to avoid floods
warn(
    "my-sink",
    "repeated failure",
    error=str(exc),
    _rate_limit_key="send-error",
)
```

Best practices:
- Component names should be specific (e.g., `"my-sink"`, `"my-enricher"`).
- Include actionable context, never secrets or PII.
- Prefer `_rate_limit_key` for hot paths.

## Patterns by Plugin Type

### Sinks

As of v0.4, sinks should **signal failures** to enable fallback and circuit breaker behavior:

```python
from fapilog.core.errors import SinkWriteError

class MySink:
    name = "my_sink"

    async def write(self, entry: dict) -> bool | None:
        try:
            await self._client.send(entry)
            return None  # Success (or return True)
        except Exception as exc:
            # Signal failure to the core - triggers fallback and circuit breaker
            raise SinkWriteError(
                f"Failed to write to {self.name}",
                sink_name=self.name,
                cause=exc,
            ) from exc
```

**Return value semantics:**

| Return | Meaning | Core action |
| --- | --- | --- |
| `None` / no return | Success | None |
| `True` | Success | None |
| `False` | Failure | Trigger fallback, increment circuit breaker |
| `SinkWriteError` raised | Failure | Trigger fallback, increment circuit breaker |

For sinks where failure cannot be detected immediately (e.g., fire-and-forget UDP, async batched delivery), emit diagnostics and return `False`:

```python
class FireAndForgetSink:
    name = "udp-sink"

    async def write(self, entry: dict) -> bool | None:
        try:
            self._socket.sendto(data, self._addr)
            return None  # Best-effort success
        except Exception as exc:
            from fapilog.core.diagnostics import warn
            warn("udp-sink", "send failed", error=str(exc))
            return False  # Signal failure
```

### Enrichers

Return an empty dict on failure so the event continues:

```python
class MyEnricher:
    name = "my_enricher"

    async def enrich(self, event: dict) -> dict:
        try:
            info = await self._lookup(event.get("user_id"))
            return {"user_email": info.email}
        except Exception as exc:
            from fapilog.core.diagnostics import warn

            warn("my-enricher", "enrichment failed", error=str(exc))
            return {}
```

### Redactors

Be conservative to avoid leaking sensitive data:

```python
class MyRedactor:
    name = "my_redactor"

    async def redact(self, event: dict) -> dict:
        try:
            return self._apply_rules(event)
        except Exception as exc:
            from fapilog.core.diagnostics import warn

            warn("my-redactor", "redaction failed; using fallback", error=str(exc))
            return {"level": event.get("level"), "message": "[REDACTION_ERROR]"}
```

### Processors

Processors should mirror sink behavior: contain errors, emit diagnostics, and return the original or partially processed payload rather than raising.

## What Fapilog Does If You Raise

Fapilog isolates plugin failures:

- **Sinks**: `SinkWriteError` (or `False` return) triggers the fallback handler (stderr by default) and increments circuit breaker counters. Other sinks still execute. This is the **expected** behavior for sink failures.
- **Enrichers/redactors/processors**: Exceptions are caught; diagnostics are emitted; the pipeline continues. These plugins should still contain their own errors for clearer diagnostics.
- **Health checks/metrics**: Failures may mark the plugin unhealthy or record errors.

No plugin failure propagates to user code.

## Health Checks Reflecting Error State

Sinks can track failures internally while still signaling them to the core:

```python
import time
from fapilog.core.errors import SinkWriteError

class MySink:
    name = "my_sink"

    def __init__(self) -> None:
        self._failures = 0
        self._last_success = 0.0

    async def write(self, entry: dict) -> bool | None:
        try:
            await self._send(entry)
            self._failures = 0
            self._last_success = time.time()
            return None
        except Exception as exc:
            self._failures += 1
            raise SinkWriteError(
                f"Failed to write to {self.name}",
                sink_name=self.name,
                cause=exc,
            ) from exc

    async def health_check(self) -> bool:
        if self._failures >= 5:
            return False
        if self._last_success and (time.time() - self._last_success) > 60:
            return False
        return True
```

## Retry for Transient Failures

Sinks can retry internally before signaling failure:

```python
from fapilog.core.errors import SinkWriteError
from fapilog.core.retry import AsyncRetrier, RetryConfig

class MySink:
    name = "my_sink"

    def __init__(self) -> None:
        self._retrier = AsyncRetrier(
            RetryConfig(max_attempts=3, base_delay=1.0, max_delay=10.0)
        )

    async def write(self, entry: dict) -> bool | None:
        try:
            await self._retrier.retry(lambda: self._send(entry))
            return None
        except Exception as exc:
            # Retries exhausted - signal failure to the core
            raise SinkWriteError(
                f"Failed to write to {self.name} after retries",
                sink_name=self.name,
                cause=exc,
            ) from exc
```

## Quick Reference

| Scenario | Action |
| --- | --- |
| Config invalid in `__init__` | Raise immediately |
| `start()` cannot acquire resources | Raise or mark unhealthy |
| Failure in sink `write()` | Raise `SinkWriteError` or return `False` |
| Failure in `enrich`/`redact`/`process` | Contain, emit diagnostics, return safe fallback |
| Transient errors (sinks) | Retry with backoff; raise `SinkWriteError` after retries |
| Transient errors (other plugins) | Retry with backoff; contain after retries |
| Repeated failures | Update health checks to report unhealthy |
