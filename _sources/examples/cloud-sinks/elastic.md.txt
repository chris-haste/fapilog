# Elastic / OpenSearch

Send JSON logs to Elastic Cloud or OpenSearch using the HTTP sink or a custom sink built on `CloudSinkBase`.

## Quick sketch

```python
from fapilog import get_logger
from fapilog.plugins.sinks.http_client import BatchFormat, HttpSink, HttpSinkConfig

sink = HttpSink(
    config=HttpSinkConfig(
        endpoint="https://elastic.example.com/_bulk",
        batch_size=100,
        batch_timeout_seconds=2.0,
        batch_format=BatchFormat.NDJSON,
    )
)
logger = get_logger(sinks=[sink])
```

- Use Basic Auth or API keys via HTTP headers.
- Batch logs into NDJSON for `_bulk` ingestion.
- Consider compression (`processor` stage) for large batches.

> For a full-featured sink, extend `CloudSinkBase` to format NDJSON, sign requests, and handle 429/503 retries.
