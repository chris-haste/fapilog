# Cookbook

Focused, SEO-friendly guides that solve specific problems. Each recipe addresses a common search query with copy-pasteable solutions.

```{toctree}
:maxdepth: 1
:titlesonly:
:caption: Cookbook

fastapi-json-logging
fastapi-request-id-logging
non-blocking-async-logging
dev-prod-logging-config
redacting-secrets-pii
safe-request-response-logging
skip-noisy-endpoints
log-sampling-rate-limiting
graceful-shutdown-flush
```

## Quick Links

- [FastAPI JSON Logging](fastapi-json-logging.md) - Unified JSON output for app and Uvicorn access logs
- [FastAPI request_id Logging](fastapi-request-id-logging.md) - Correlation ID middleware that works with async
- [Non-blocking Async Logging](non-blocking-async-logging.md) - Protect latency with backpressure modes
- [Dev + Prod Logging Config](dev-prod-logging-config.md) - Single config that adapts to environment
- [Redacting Secrets and PII](redacting-secrets-pii.md) - Secure defaults and custom redaction patterns
- [Safe Request/Response Logging](safe-request-response-logging.md) - Body logging without hanging or breaking streaming
- [Skipping Health/Metrics Endpoints](skip-noisy-endpoints.md) - Reduce log noise from health checks
- [Log Sampling and Rate Limiting](log-sampling-rate-limiting.md) - Control log volume during traffic spikes
- [Graceful Shutdown & Flushing Logs](graceful-shutdown-flush.md) - Don't lose logs on deploy
