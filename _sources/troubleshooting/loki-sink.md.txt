# Loki Sink Issues

Common problems when sending logs to Grafana Loki.

## Rate limiting (429)

- **Cause:** Loki throttling when ingesting too fast.
- **Fix:** Lower `batch_size`, increase `batch_timeout_seconds`, or reduce log volume. The sink backs off automatically using `retry_base_delay`.

## Client errors (400/401/403)

- **Cause:** Invalid payload, missing auth, or tenant mismatch.
- **Fix:** Verify `url`, `tenant_id`, and auth settings. Check diagnostics for the response snippet. Ensure labels are valid (`[A-Za-z0-9_-]` only).

## Connection errors/timeouts

- **Cause:** Loki not reachable or slow.
- **Fix:** Confirm `FAPILOG_LOKI__URL`, container health, and network egress. Increase `timeout_seconds` if necessary.

## Missing logs

- Ensure labels used in queries match the configured static labels and `label_keys`.
- Remember to wait briefly after writes for Loki to index (tests sleep ~1s).
- Pair with `size_guard` if upstream payloads can exceed target limits before HTTP push.
