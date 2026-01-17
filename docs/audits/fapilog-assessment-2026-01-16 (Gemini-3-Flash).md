# Fapilog Assessment Report (2026-01-16)

## Phase 0 — Context & Scope

**A) Library Name & Context**
*   **Name:** `fapilog`
*   **Version Signal:** `Beta` (as per `pyproject.toml` and `README.md`). The repository uses VCS-based versioning via `hatch-vcs`.
*   **Language:** Python 3.9+ (Type-hinted, `py.typed` included).
*   **Domain:** Production-ready, async-first structured logging for the modern Python stack (specifically optimized for FastAPI and cloud-native environments).

**B) Primary User Personas**
*   **Application Developers:** Using it for standard structured logging in FastAPI/async apps.
*   **Platform/SRE Teams:** Leveraging backpressure, circuit breakers, and metrics for operational stability.
*   **Data/Compliance Engineers:** Utilizing redaction stages and the `fapilog-tamper` add-on for audit integrity.

**C) Intended Runtime Contexts**
*   **Server (FastAPI/Starlette):** Primary target via `LoggingMiddleware` and async-first design.
*   **Serverless/Cloud:** Sinks for CloudWatch and Loki; lightweight enough for Lambda if batching is tuned.
*   **Enterprise/On-prem:** Database sinks (Postgres) and tamper-evident logging for compliance.

---

## Phase 1 — Repo Inventory & Health

### Repo Snapshot
*   `src/fapilog/`: Core logic and plugin ecosystem.
*   `src/fapilog/core/`: Internal worker, settings (Pydantic v2), serialization (orjson), and concurrency primitives (ring queue).
*   `src/fapilog/plugins/`: Pluggable architecture for Sinks, Enrichers, Redactors, and Processors.
*   `tests/`: Comprehensive test suite (90%+ coverage) including unit, integration, and property-based tests.
*   `docs/`: Extensive Markdown documentation covering architecture, user guides, and reliability.
*   `examples/`: Docker-composed examples for Loki, Postgres, and CloudWatch.

### Packaging & Build
*   **Build System:** `hatch` / `hatchling`.
*   **Dependencies:** Pydantic v2, `pydantic-settings`, `httpx`, `orjson`, `packaging`.
*   **Optional Extras:** `fastapi`, `aws` (boto3), `metrics` (prometheus-client), `postgres` (asyncpg).

### Maintenance Signals
*   **Activity:** Extremely high. Recent commits (Jan 15, 2026) show active refactoring (plugin normalization) and documentation updates.
*   **Bus Factor:** Chris Haste appears to be the primary maintainer, but the project has a professional structure (CODEOWNERS, contributing guides).
*   **CI/CD:** Robust GitHub Actions pipelines for linting (`ruff`), type checking (`mypy`), testing (`pytest`), and security scanning (`nightly.yml`, `security-sbom.yml`).

---

## Phase 2 — Capabilities Discovery

### Capability Catalog

| Capability | Advertised? | Evidence | Maturity | Notes |
| :--- | :---: | :--- | :--- | :--- |
| **Async Worker** | Y | `src/fapilog/core/worker.py` | Stable | Non-blocking background log draining. |
| **Backpressure** | Y | `src/fapilog/core/concurrency.py` | Stable | Configurable drop/wait policies. |
| **FastAPI Middleware** | Y | `src/fapilog/fastapi/logging.py` | Stable | Request/response logging with correlation IDs. |
| **Redaction (PII)** | Y | `src/fapilog/plugins/redactors/` | Stable | Recursive masking with safety guardrails. |
| **Adaptive Batching** | N | `src/fapilog/core/adaptive.py` | Beta | Dynamically scales batches based on sink latency. |
| **Circuit Breakers** | N | `src/fapilog/core/circuit_breaker.py` | Beta | Prevents overloading failing sinks. |
| **Tamper-Evident Logs** | Y | `packages/fapilog-tamper/` | Enterprise | Integrity signatures and MACs. |
| **Zero-Copy Processors**| N | `src/fapilog/plugins/processors/zero_copy.py` | Beta | Memoryview-based optimizations. |

### Boundaries & Gotchas
*   **Non-Goal:** High-speed local logging (e.g., millions of logs/sec to a fast SSD). Stdlib or `picologging` may be faster due to lower abstraction overhead.
*   **Gotcha:** **Event Loop Dependency.** As an async-first library, it requires a running event loop for the background worker. Shutdown sequences must be handled carefully (documented in `docs/stories/5.30.document-event-loop-lifecycle.md`).

---

## Phase 3 — Technical Assessment

### Architecture Overview
The library follows a **Pipeline Architecture**:
`Log Call` → `Queue` → `Worker` → `Filters` → `Enrichers` → `Redactors` → `Processors` → `Sinks`.

*   **Concurrency:** Uses a custom `NonBlockingRingQueue` (`src/fapilog/core/concurrency.py`) to minimize lock contention between the app and the worker.
*   **Error Handling:** Excellent containment. Each stage in `LoggerWorker._flush_batch` is wrapped to ensure a single failing plugin doesn't stop the pipeline.

### Code Quality Review
*   **Organization:** Highly modular. Clear separation between core (infrastructure) and plugins (functionality).
*   **Typing:** Strict MyPy configuration (`disallow_untyped_defs = true`).
*   **Complexity Hotspot:** `src/fapilog/core/worker.py` is the engine room; it's complex but well-commented and defensive.

### Security Posture
*   **Redaction Safety:** `FieldMaskRedactor` includes `max_depth` (default 16) and `max_keys_scanned` (default 1000) to prevent DoS via malicious deeply-nested log objects.
*   **Supply Chain:** Uses `security-sbom.yml` and pinned dependencies in CI.

---

## Phase 4 — Documentation Quality

*   **Onboarding:** Strong. `README.md` provides clear "Quick Start" and "Why fapilog?" sections.
*   **Completeness:** Docstrings are present for most public APIs. The `docs/` directory is vast, including ADR-like "stories" which provide historical context for decisions.
*   **Examples:** High quality. Includes `docker-compose.yml` files for integration testing sinks (Postgres, Loki).

---

## Phase 5 — Developer Experience (DX) Review

*   **Ergonomics:** `get_logger(preset="production")` simplifies complex configurations.
*   **Diagnostics:** Internal diagnostics (via `fapilog.core.diagnostics.warn`) provide visibility into worker failures without crashing the host app.
*   **IDE Friendliness:** Full typing and `py.typed` ensure excellent autocomplete in VS Code/PyCharm.
*   **DX Score: 9/10.** The library is "delightful" due to its sensible defaults and clear error boundaries.

---

## Phase 6 — Competitor Landscape

| Competitor | Relevance | Differentiator |
| :--- | :--- | :--- |
| **Structlog** | Market Leader | fapilog is more "batteries-included" for async/FastAPI; Structlog is more general-purpose. |
| **Loguru** | Popularity | Loguru is easier for simple scripts; fapilog is better for cloud-native reliability. |
| **aiologger** | Async-focus | aiologger is lower-level; fapilog provides a full enrichment/redaction pipeline. |
| **picologging** | Performance | picologging focuses on raw speed; fapilog focuses on async safety and backpressure. |

---

## Phase 7 — Red Flags & Risk Register

| Risk | Severity | Likelihood | Evidence | Mitigation |
| :--- | :---: | :---: | :--- | :--- |
| **Loop Stalls** | P1 | Low | `src/fapilog/core/worker.py` | Worker uses `asyncio.sleep(0.001)` to yield; well-tested in CI. |
| **Memory Pressure**| P2 | Med | `NonBlockingRingQueue` | Configurable `max_queue_size` and drop policies. |
| **Bus Factor** | P2 | Med | GitHub commit history | Chris Haste is the dominant contributor. |

---

## Phase 8 — Verdict & Decision Guidance

**Verdict: ADOPT (for FastAPI/Async Cloud Apps)**

### Fit-by-Scenario
*   **Best Fit:** FastAPI microservices, high-traffic async APIs, environments requiring PII redaction.
*   **Poor Fit:** Simple CLI scripts, synchronous Django/Flask apps (overhead not worth it).

### Adoption Checklist
1. [ ] Spike: Verify `FAPILOG_CORE__DROP_ON_FULL` behavior under simulated sink failure.
2. [ ] Config: Define `fields_to_mask` for PII compliance.
3. [ ] Monitor: Export fapilog metrics to Prometheus to track queue depth.

---

## APPENDIX: SCORING RUBRIC

### 1) Score Summary Table

| Category | Weight | Score (0–10) | Weighted Points | Confidence | Evidence Pointers |
| :--- | :---: | :---: | :---: | :---: | :--- |
| Capability Coverage | 20 | 9 | 18.0 | High | `src/fapilog/plugins/` |
| Tech Architecture | 18 | 9 | 16.2 | High | `src/fapilog/core/worker.py` |
| Documentation | 14 | 9 | 12.6 | High | `docs/`, `README.md` |
| Developer Experience | 16 | 9 | 14.4 | High | `src/fapilog/core/presets.py` |
| Security Posture | 12 | 8 | 9.6 | High | `FieldMaskRedactor` guardrails |
| Performance | 8 | 7 | 5.6 | Med | `benchmarking.py` (simulated) |
| Reliability | 6 | 8 | 4.8 | High | `circuit_breaker.py`, `retry.py` |
| Project Health | 6 | 8 | 4.8 | High | Git log (2026-01-15 commits) |

### 2) Final Score
*   **Weighted Score:** **86.0 / 100**
*   **Confidence Level:** **High**. Extensive evidence from code, tests, and active maintenance.

### 3) Gate Check
*   **P0 Avoid Gates:** None triggered.
*   **P1 Trial-only Gates:** None triggered. (The "Experimental" plugin marketplace is clearly marked).
*   **Resulting Verdict:** **Adopt.**

### 4) “If I had 2 hours” Validation Plan
1.  **Test Backpressure:** Run a FastAPI app with a slow HTTP sink (simulated delay). Load test with 10k requests. Check if `drop_on_full=true` correctly prevents memory explosion.
2.  **Verify Redaction:** Pass a 20-level nested dictionary with "password" at the bottom. Confirm `max_depth` stops the traversal and logs a diagnostic warning.
3.  **Check Shutdown:** Force a `SIGTERM` while logs are in the queue. Confirm the `drained_event` in `LoggerWorker` allows logs to flush before the process exits.
