# 📌 Fapilog Milestone Tracker

## Prometheus Exporter Integration Example (FastAPI)

Expose Prometheus metrics from the collector's isolated registry via FastAPI:

```python
from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from fapilog.core.observability import (
    ObservabilitySettings,
    create_metrics_collector_from_settings,
)

app = FastAPI()
metrics = create_metrics_collector_from_settings(
    ObservabilitySettings(metrics={"enabled": True, "exporter": "prometheus"})
)

@app.get("/metrics")
async def metrics_endpoint() -> Response:
    registry = metrics.registry
    if registry is None:
        return Response(status_code=204)
    data = generate_latest(registry)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
```

Notes:

- The collector is container-scoped; this example wires a process-level instance for demonstration.
- For production, create the collector from your container settings and inject it where needed.

This document outlines the prioritized roadmap for `fapilog`, including core development, FastAPI integration, enterprise plugin support, and documentation milestones.

---

## 🧱 Milestone 1: Core Logging Engine (MVP)

**Description:**  
Establish the async-safe, plugin-based foundation for all other features.

**Goal:**  
A working logger with plugin support, contextual logging, and console output.

**Deliverables:**

- [ ] `AsyncLogger` class with structured methods (`info`, `warn`, `error`, etc.)
- [ ] Logging container with context scoping
- [ ] Context management (`correlation_id`, `trace_id`)
- [ ] Console sink plugin
- [ ] JSON formatter plugin
- [ ] Basic redaction processor (e.g., for PII masking)
- [ ] In-memory sink for test environments
- [ ] Unit test coverage for all components

**Estimated Duration:** 1.5–2 weeks

---

## 🚀 Milestone 2: FastAPI Integration (`fapilog-fastapi`)

**Description:**  
Deliver first-class FastAPI support to drive early adoption and usability.

**Goal:**  
Plug-and-play integration with FastAPI apps, including middleware and DI.

**Deliverables:**

- [ ] `FapilogMiddleware` for request-aware logger injection
- [ ] Logger dependency via FastAPI `Depends`
- [ ] Request/response logging plugin
- [ ] Exception logging for unhandled or validation errors
- [ ] Lifecycle hook registration (e.g., `startup`, `shutdown`)
- [ ] Test fixture for log capture during FastAPI tests
- [ ] FastAPI example app using `fapilog-fastapi`
- [ ] Quickstart guide in README

**Estimated Duration:** 1.5–2 weeks

---

## 🧪 Milestone 3: Testing & Compatibility Hardening

**Description:**  
Strengthen quality via high test coverage, linting, and CI pipeline integration.

**Goal:**  
Ensure correctness, concurrency safety, and multi-version support.

**Deliverables:**

- [ ] > 90% test coverage
- [ ] Concurrency stress tests (e.g., `asyncio.gather`)
- [ ] Pre-commit hooks: `ruff`, `black`, `mypy`, `pytest`
- [ ] GitHub Actions workflow for CI
- [ ] Python version matrix (3.8 to 3.12+)
- [ ] GitHub badge for test coverage

**Estimated Duration:** 1 week

---

## 🏗️ Milestone 4: Production-Grade Plugins

**Description:**  
Add sinks and processors required for enterprise-grade deployment.

**Goal:**  
Support cloud-native, secure, and performant logging use cases.

**Deliverables:**

- [ ] Loki sink with async batching
- [ ] File sink with rotation support
- [ ] Severity-level filtering plugin
- [ ] Structured redaction (deep keys, regex patterns)
- [ ] Prometheus-compatible metrics exporter
- [ ] Performance benchmarks and latency profiling

**Estimated Duration:** 2–2.5 weeks

---

## 📚 Milestone 5: Documentation, Examples, and Launch

**Description:**  
Prepare official documentation and usage examples for public release.

**Goal:**  
Enable adoption, contribution, and discoverability.

**Deliverables:**

- [ ] ReadTheDocs or GitHub Pages site
- [ ] "Why Fapilog?" positioning page
- [ ] Usage documentation for CLI, FastAPI, and services
- [ ] Plugin authoring guide
- [ ] Example: Dockerized FastAPI app with Loki
- [ ] Example: Async service with structured logs

**Estimated Duration:** 1 week

---

## 🧩 Optional Future Milestones (Backlog)

- `fapilog-django`: Middleware and handler integration for Django
- `fapilog-celery`: Task-level logging + worker-level context
- `fapilog-lambda`: Lightweight AWS Lambda compatibility
- OpenTelemetry tracing integration
- Hosted SaaS frontend (log explorer/alerting)

---

## 📊 Summary

| Milestone                 | Priority  | Duration | Key Outcome                      |
| ------------------------- | --------- | -------- | -------------------------------- |
| Core Logging Engine (MVP) | ⭐️ High  | 2 weeks  | Async logger + plugin system     |
| FastAPI Integration       | ⭐️ High  | 2 weeks  | `fapilog-fastapi` ready to use   |
| Testing & Compatibility   | ✅ Medium | 1 week   | CI ready + cross-version support |
| Production-Grade Plugins  | ✅ Medium | 2 weeks  | Loki, file, metrics, redaction   |
| Docs, Examples, Launch    | ✅ Medium | 1 week   | Public-ready with examples       |

---
