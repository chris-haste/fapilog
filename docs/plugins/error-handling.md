# Plugin Error Handling

Guidance for containing errors in sinks, enrichers, redactors, and processors without breaking the logging pipeline.

## Core Principle: Contain Errors

Plugins must not leak exceptions into the core pipeline from `write()`, `enrich()`, `redact()`, or `process()`. Handle failures locally, emit diagnostics, and return a safe fallback so other plugins keep running.

## When Raising Is Acceptable

- `__init__`: Reject invalid configuration or missing dependencies.
- `start()`: Fail fast if required resources cannot be acquired (or contain and mark unhealthy).
- All other methods: contain errors; do not re-raise into the pipeline.

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

```python
class MySink:
    name = "my-sink"

    def __init__(self) -> None:
        self._failures = 0
        self._last_error: str | None = None

    async def write(self, entry: dict) -> None:
        try:
            await self._client.send(entry)
            self._failures = 0
            self._last_error = None
        except Exception as exc:
            from fapilog.core.diagnostics import warn

            warn(
                "my-sink",
                "failed to send log",
                error=str(exc),
                level=entry.get("level"),
            )
            self._failures += 1
            self._last_error = str(exc)
            # Do not re-raise; other sinks still run
```

### Enrichers

Return an empty dict on failure so the event continues:

```python
class MyEnricher:
    name = "my-enricher"

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
    name = "my-redactor"

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

Fapilog isolates plugin failures, but this is a fallback:

- Enrichers/redactors: Exceptions are caught; diagnostics are emitted; the pipeline continues.
- Sinks: Fanout contains errors per sink; other sinks still execute.
- Health checks/metrics: Failures may mark the plugin unhealthy or record errors.

Well-behaved plugins should still contain their own errors for clearer diagnostics and lower overhead.

## Health Checks Reflecting Error State

```python
import time

class MySink:
    name = "my-sink"

    def __init__(self) -> None:
        self._failures = 0
        self._last_success = 0.0

    async def write(self, entry: dict) -> None:
        try:
            await self._send(entry)
            self._failures = 0
            self._last_success = time.time()
        except Exception:
            self._failures += 1

    async def health_check(self) -> bool:
        if self._failures >= 5:
            return False
        if self._last_success and (time.time() - self._last_success) > 60:
            return False
        return True
```

## Retry for Transient Failures

```python
from fapilog.core.retry import AsyncRetrier, RetryConfig

class MySink:
    def __init__(self) -> None:
        self._retrier = AsyncRetrier(
            RetryConfig(max_attempts=3, base_delay=1.0, max_delay=10.0)
        )

    async def write(self, entry: dict) -> None:
        try:
            await self._retrier.retry(lambda: self._send(entry))
        except Exception as exc:
            from fapilog.core.diagnostics import warn

            warn("my-sink", "retries exhausted", error=str(exc))
            # Contain the error after retries
```

## Quick Reference

| Scenario | Action |
| --- | --- |
| Config invalid in `__init__` | Raise immediately |
| `start()` cannot acquire resources | Raise or mark unhealthy |
| Failure in `write`/`enrich`/`redact`/`process` | Contain, emit diagnostics, return safe fallback |
| Transient errors | Retry with backoff; contain after retries |
| Repeated failures | Update health checks to report unhealthy |
