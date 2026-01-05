# Grafana Loki

Send logs to Grafana Loki using the built-in `loki` sink.

## Quick start

```bash
docker run -d -p 3100:3100 grafana/loki:latest
export FAPILOG_CORE__SINKS='["loki"]'
export FAPILOG_LOKI__URL=http://localhost:3100
python - <<'PY'
from fapilog import get_logger
logger = get_logger()
logger.info("hello loki", component="demo")
PY
```

Query:

```bash
curl -G http://localhost:3100/loki/api/v1/query --data-urlencode 'query={service="fapilog"}'
```

See `docs/plugins/sinks/loki.md` for full configuration and `examples/loki_logging` for a complete FastAPI + Docker Compose setup.
