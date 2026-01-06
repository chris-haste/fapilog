# PostgreSQL logging example

FastAPI app that sends logs to PostgreSQL using the `postgres` sink.

## Prerequisites

- Docker + Docker Compose
- Python 3.10+ (optional for running locally without Docker)

## Run with Docker Compose

```bash
docker compose up --build
```

The stack starts:

- `postgres` (listening on 5432, database `fapilog`)
- `app` (FastAPI, listening on 8000)

Once running, hit the app and generate logs:

```bash
curl http://localhost:8000/
curl http://localhost:8000/users/42
```

Inspect logs in PostgreSQL:

```bash
psql -h localhost -U fapilog -d fapilog -c "SELECT level, message, timestamp FROM logs ORDER BY timestamp DESC LIMIT 5;"
```

Sample queries are in `queries.sql`.

## Run locally (without Docker)

1. Start PostgreSQL and set env vars:

```bash
export FAPILOG_POSTGRES__HOST=localhost
export FAPILOG_POSTGRES__DATABASE=fapilog
export FAPILOG_POSTGRES__USER=fapilog
export FAPILOG_POSTGRES__PASSWORD=fapilog
export FAPILOG_CORE__SINKS='["postgres"]'
```

2. Install deps and run the app:

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```
