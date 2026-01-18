---
orphan: true
---

# Tenacity Integration Guide

Fapilog's retry infrastructure is intentionally lightweight to avoid pulling in extra dependencies at import time. For teams that already standardize on [Tenacity](https://tenacity.readthedocs.io), the sinks expose a `RetryCallable` protocol so you can plug in your own retry implementation without adding Tenacity as a core dependency.

## The `RetryCallable` protocol

Any async callable that implements:

```python
async def __call__(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
    ...
```

can be passed to sink configurations (`HttpSinkConfig.retry`, `WebhookSinkConfig.retry`) or to `AsyncHttpSender`. Fapilog's built-in `AsyncRetrier` already implements this protocol.

## Adapting Tenacity

Tenacity's `AsyncRetrying` iterator can be adapted with a tiny wrapper:

```python
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential
from fapilog.plugins.sinks import HttpSink


class TenacityAdapter:
    """Adapt Tenacity to Fapilog's RetryCallable protocol."""

    def __init__(self, retrying: AsyncRetrying):
        self._retrying = retrying

    async def __call__(self, func, *args, **kwargs):
        async for attempt in self._retrying:
            with attempt:
                return await func(*args, **kwargs)


sink = HttpSink(
    endpoint="https://api.example.com/logs",
    retry=TenacityAdapter(
        AsyncRetrying(
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=1, max=30),
        )
    ),
)
```

Because the adapter satisfies `RetryCallable`, sinks will invoke it in place of the built-in retrier.
