# Building HTTP-Based Sinks

HTTP sinks (Loki, Datadog HTTP intake, Splunk HEC, Elastic ingest) share a core pattern:

1. **Async HTTP client:** use `httpx.AsyncClient` with timeouts.
2. **Batching:** accumulate events with size/time triggers; respect provider limits.
3. **Authentication:** support bearer tokens or basic auth via headers.
4. **Retry/backoff:** handle 429/5xx with exponential backoff; emit diagnostics.
5. **Circuit breaker:** contain repeated failures per sink.
6. **Fast path:** implement `write_serialized` when the sink consumes raw bytes/strings.

Reference implementations:

- `fapilog.plugins.sinks.contrib.loki` (Grafana Loki HTTP push)
- `docs/plugins/sinks/loki.md` (configuration)
- `tests/integration/test_loki_sink.py` (Docker-backed CI pattern)

Testing tips:

- Use dockerized services (Loki) in CI; gate tests on env vars to avoid local failures.
- Stub the HTTP client in unit tests to avoid network calls and assert payload shapes.
- Enable `FAPILOG_CORE__INTERNAL_LOGGING_ENABLED=true` when capturing diagnostics during tests.
