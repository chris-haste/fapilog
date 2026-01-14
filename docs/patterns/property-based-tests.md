# Property-Based Tests

Use Hypothesis to validate invariants across a wide input space. Property tests
live under `tests/property` and are marked with `@pytest.mark.property` for easy
selection.

## Guidelines

- Keep strategies focused and JSON-safe when targeting serialization paths.
- Limit input sizes to keep tests fast.
- Prefer deterministic assertions over inspecting private state.
- Use shared strategies from `tests/property/strategies.py` when possible.
- Do NOT use per-test `@settings(max_examples=...)` overrides. CI controls
  example counts via `HYPOTHESIS_MAX_EXAMPLES` (see `tox.ini`).

## Example

```python
import pytest
from hypothesis import given

from fapilog.core.serialization import serialize_mapping_to_json_bytes

from tests.property.strategies import json_dicts


@pytest.mark.property
@given(payload=json_dicts)
def test_json_serialization_round_trip(payload: dict) -> None:
    view = serialize_mapping_to_json_bytes(payload)
    assert view.data
```

## Running Locally

```bash
# Default (uses tox.ini value of 100 examples):
pytest -m property

# Quick smoke test:
HYPOTHESIS_MAX_EXAMPLES=10 pytest -m property

# Thorough local testing:
HYPOTHESIS_MAX_EXAMPLES=500 pytest -m property
```
