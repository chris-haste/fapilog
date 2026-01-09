# Property-Based Tests

Use Hypothesis to validate invariants across a wide input space. Property tests
live under `tests/property` and are marked with `@pytest.mark.property` for easy
selection.

## Guidelines

- Keep strategies focused and JSON-safe when targeting serialization paths.
- Limit input sizes and use `@settings(max_examples=...)` to control runtime.
- Prefer deterministic assertions over inspecting private state.
- Use shared strategies from `tests/property/strategies.py` when possible.
- CI caps example counts via `HYPOTHESIS_MAX_EXAMPLES` (see `tox.ini`).

## Example

```python
import pytest
from hypothesis import given, settings

from fapilog.core.serialization import serialize_mapping_to_json_bytes

from tests.property.strategies import json_dicts


@pytest.mark.property
@given(payload=json_dicts)
@settings(max_examples=200)
def test_json_serialization_round_trip(payload: dict) -> None:
    view = serialize_mapping_to_json_bytes(payload)
    assert view.data
```

## Running Locally

```bash
python -m pytest -m property
```
