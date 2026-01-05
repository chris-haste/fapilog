# Building SDK-Based Sinks

SDK-based sinks (CloudWatch, GCP Logging, Azure Monitor, Kafka client APIs) share a few patterns:

1) **Lazy import SDKs** so core installs don't pull heavy dependencies.
2) **Wrap blocking calls** with `asyncio.to_thread()` to keep the event loop responsive.
3) **Batch intentionally** and enforce provider limits (event count, payload size).
4) **Handle provider-specific errors** with retries/backoff (e.g., sequence tokens, throttling).
5) **Add circuit breakers** to contain repeated failures.
6) **Emit diagnostics** with rate limits; never let sink errors crash the pipeline.

Reference implementations:

- `fapilog.plugins.sinks.contrib.cloudwatch` (CloudWatch Logs, boto3)
- `tests/integration/test_cloudwatch_sink_localstack.py` (LocalStack testing pattern)
- `examples/cloudwatch_logging` (FastAPI + LocalStack)

Suggested scaffold:

```python
from fapilog.core import diagnostics
from fapilog.plugins.sinks._batching import BatchingMixin

class MySdkSink(BatchingMixin):
    name = "my_sink"

    async def start(self):
        # Lazy import + client creation
        ...

    async def write(self, entry: dict):
        await self._enqueue_for_batch(self._to_event(entry))

    async def _send_batch(self, batch: list[dict]):
        # Chunk, sort, retry, and respect provider limits
        ...
```

Testing tips:

- Use provider stubs/fakes (or SDK stubbers) to avoid network calls in unit tests.
- Add optional integration tests gated on environment variables (LocalStack).
- Enable `FAPILOG_CORE__INTERNAL_LOGGING_ENABLED=true` when capturing diagnostics in tests.
