---
orphan: true
---

# Code Coverage Report

**Date:** 2026-01-16  
**Scope:** Current repository test suite coverage (statements + branches), excluding `flaky` tests  
**Tooling:** `pytest`, `pytest-cov`, `coverage.py` (JSON: 7.10.2), branch coverage enabled

---

## Executive Summary

- **Overall coverage (statements + branches):** **90.88%** (meets 90% gate)
- **Statements:** 8,140 / 8,776 covered (**92.75%**), 636 missing
- **Branches:** 2,024 / 2,408 covered (**84.05%**), 384 missing (308 partial)
- **Key gaps:** CloudWatch sink branch paths, core logger/worker lifecycle/error paths, validator edge-cases

---

## Method (Reproducible)

Coverage was collected using `pytest-cov` with branch coverage and XML output, then summarized from `coverage.json`.

```bash
hatch run test:test -- tests -m "not flaky" --cov=src/fapilog --cov-branch --cov-report=term-missing --cov-report=xml
hatch run test:python -m coverage json -o coverage.json
```

Notes:
- Some tests include strict **timing/throughput assertions**. When running under coverage (especially on slower machines), those tests may become flaky unless they are explicitly skipped by their existing env guards or excluded by marker selection in CI workflows.

---

## Coverage by Top-Level Package (statements + branches)

| Package | Covered / Total | Coverage |
| --- | ---:| ---:|
| `src/fapilog/metrics/` | 256 / 290 | 88.28% |
| `src/fapilog/sinks/` | 16 / 18 | 88.89% |
| `src/fapilog/plugins/` | 3,676 / 4,125 | 89.12% |
| `src/fapilog/testing/` | 579 / 645 | 89.77% |
| `src/fapilog/core/` | 4,405 / 4,797 | 91.83% |
| `src/fapilog/` (root modules) | 605 / 659 | 91.81% |
| `src/fapilog/fastapi/` | 279 / 294 | 94.90% |
| `src/fapilog/containers/` | 194 / 199 | 97.49% |
| `src/fapilog/caching/` | 151 / 154 | 98.05% |
| `src/fapilog/cli/` | 3 / 3 | 100.00% |

---

## Lowest-Covered Files (statements + branches)

Top 15 lowest by combined coverage:

| File | Coverage | Missing (stmts) | Missing (branches) |
| --- | ---:| ---:| ---:|
| `src/fapilog/plugins/sinks/contrib/cloudwatch.py` | 67.02% | 53 | 41 |
| `src/fapilog/_version.py` | 75.00% | 4 | 1 |
| `src/fapilog/core/worker.py` | 81.19% | 55 | 18 |
| `src/fapilog/plugins/redactors/field_mask.py` | 81.72% | 16 | 18 |
| `src/fapilog/plugins/sinks/webhook.py` | 83.46% | 14 | 7 |
| `src/fapilog/testing/validators.py` | 83.77% | 24 | 25 |
| `src/fapilog/plugins/filters/__init__.py` | 83.82% | 8 | 3 |
| `src/fapilog/plugins/loader.py` | 84.07% | 20 | 9 |
| `src/fapilog/core/logger.py` | 84.27% | 69 | 21 |
| `src/fapilog/plugins/redactors/url_credentials.py` | 84.27% | 9 | 5 |
| `src/fapilog/core/errors.py` | 84.98% | 36 | 14 |
| `src/fapilog/plugins/redactors/regex_mask.py` | 85.25% | 13 | 5 |
| `src/fapilog/plugins/sinks/http_client.py` | 85.91% | 16 | 5 |
| `src/fapilog/plugins/sinks/stdout_json.py` | 86.67% | 10 | 2 |
| `src/fapilog/plugins/filters/rate_limit.py` | 87.04% | 10 | 4 |

---

## Biggest Absolute Gaps (missed statements + missed branches)

Top 10 by absolute misses:

| File | Missed / Total | Coverage |
| --- | ---:| ---:|
| `src/fapilog/plugins/sinks/contrib/cloudwatch.py` | 94 / 285 | 67.02% |
| `src/fapilog/core/logger.py` | 90 / 572 | 84.27% |
| `src/fapilog/core/worker.py` | 73 / 388 | 81.19% |
| `src/fapilog/core/errors.py` | 50 / 333 | 84.98% |
| `src/fapilog/testing/validators.py` | 49 / 302 | 83.77% |
| `src/fapilog/plugins/sinks/rotating_file.py` | 42 / 353 | 88.10% |
| `src/fapilog/metrics/metrics.py` | 34 / 290 | 88.28% |
| `src/fapilog/plugins/redactors/field_mask.py` | 34 / 186 | 81.72% |
| `src/fapilog/__init__.py` | 33 / 443 | 92.55% |
| `src/fapilog/core/audit.py` | 29 / 388 | 92.53% |

---

## Recommended Next Improvements (Highest ROI)

1. **CloudWatch sink (`src/fapilog/plugins/sinks/contrib/cloudwatch.py`)**
   - Target retry/error branches, credential/region config edge-cases, and failure signaling paths.

2. **Worker and core lifecycle (`src/fapilog/core/worker.py`, `src/fapilog/core/logger.py`)**
   - Add tests around shutdown/drain ordering, cancellation paths, and “sink write fails mid-batch” scenarios.

3. **Validators and branch-heavy edge cases (`src/fapilog/testing/validators.py`, redactors)**
   - Focus on malformed inputs, early-exit logic, and policy/decision branches that are hard to hit in “happy path” tests.

---

## Appendix: Totals (from `coverage.json`)

- **Percent covered (combined):** 90.8798%
- **Statements:** 8,776 total; 8,140 covered; 636 missing
- **Branches:** 2,408 total; 2,024 covered; 384 missing; 308 partial

