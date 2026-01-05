# Loki Logging Example

Run Loki and Grafana locally and send logs from a FastAPI app using the built-in Loki sink.

## Prereqs

- Docker & Docker Compose
- Python 3.11+

## Quick start

```bash
docker-compose up -d
export FAPILOG_CORE__SINKS='["loki"]'
export FAPILOG_LOKI__URL=http://localhost:3100
uvicorn main:app --reload
```

Hit `http://localhost:8000/` to generate logs.

## View logs in Grafana

1. Open http://localhost:3000 (Grafana, anonymous admin access enabled)
2. Go to **Dashboards** → **Fapilog Logs** (pre-provisioned)
3. Or use **Explore** with Loki datasource and query:

```
{service="example-app"}
```

## Query Loki directly

```bash
curl -G http://localhost:3100/loki/api/v1/query --data-urlencode 'query={service="example-app"}'
```

## Dashboard

A pre-built Grafana dashboard is included at `dashboards/fapilog-logs.json` with:

- All logs stream
- Log volume by level (time series)
- Errors-only panel

## Files

- `docker-compose.yml` - Loki + Grafana services
- `provisioning/` - Grafana auto-provisioning for datasources and dashboards
- `dashboards/fapilog-logs.json` - Pre-built dashboard JSON
- `main.py` - FastAPI example app
- `requirements.txt` - Python dependencies
