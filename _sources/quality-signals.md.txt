# Quality Signals

## Test coverage (current snapshot)
- Lines covered: 5771 / 6409 (≈90.0%) from the latest `coverage.xml`
- Test suite: 100+ unit/integration/benchmark tests under `tests/`

## How to reproduce locally

```bash
pip install fapilog[dev]
python -m pytest --cov=src/fapilog --cov-report=term
```

## Reliability defaults

See `docs/user-guide/reliability-defaults.md` for backpressure, drop policy, and redaction defaults.
