# Contract Testing

Contract tests verify schema compatibility between producers and consumers in the logging pipeline. They catch schema drift early, before it causes runtime failures.

## Why Contract Tests?

The fapilog pipeline has distinct stages:

1. **Producer**: `build_envelope()` creates log events with a defined schema
2. **Consumer**: `serialize_envelope()` serializes events expecting that schema

If these stages disagree on the data shape, logs may be lost or corrupted. Contract tests ensure the producer and consumer always agree.

### Historical Context

Contract testing was introduced after identifying a schema mismatch between `build_envelope()` and `serialize_envelope()`. The mismatch went undetected because:

- Unit tests tested each function in isolation
- Property tests used synthetic data, not real `build_envelope()` output
- The fallback serialization path masked the schema drift

Contract tests prevent this class of bug by testing the actual producer/consumer interface.

## Running Contract Tests

```bash
# Run all contract tests
pytest tests/contract/ -v

# Run with strict serialization (fail on fallback)
pytest tests/contract/ -v --strict-serialization
```

In CI, contract tests run as a separate job labeled "Contract Tests (Schema Compatibility)" and block PR merges if they fail.

## Writing Contract Tests

### Roundtrip Tests

Test that producer output is valid consumer input:

```python
from fapilog.core.envelope import build_envelope
from fapilog.core.serialization import serialize_envelope

def test_build_envelope_output_is_serializable():
    """build_envelope() output must be valid serialize_envelope() input."""
    envelope = build_envelope(level="INFO", message="test")

    # Should NOT raise - if it does, schemas have drifted
    view = serialize_envelope(envelope)
    assert view is not None
```

### Schema Validation Tests

Validate output against the JSON schema:

```python
import json
import jsonschema

def test_serialized_output_validates_against_schema(envelope_schema):
    """Serialized envelope must conform to published JSON schema."""
    envelope = build_envelope(level="INFO", message="test")
    view = serialize_envelope(envelope)
    parsed = json.loads(view.data)

    # Should not raise ValidationError
    jsonschema.validate(parsed, envelope_schema)
```

### Property Tests with Real Data

Use `build_envelope()` in property tests instead of synthetic data:

```python
from hypothesis import given
from hypothesis import strategies as st

@given(
    level=st.sampled_from(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    message=st.text(min_size=1, max_size=200),
)
def test_build_then_serialize_never_raises(level, message):
    """Property: serialize_envelope(build_envelope(...)) never raises."""
    envelope = build_envelope(level=level, message=message)
    view = serialize_envelope(envelope)
    assert view is not None
```

## The `strict_serialization` Fixture

Use this fixture to fail tests if the fallback serialization path is triggered:

```python
def test_normal_logging_uses_envelope_path(strict_serialization, logger):
    """Normal logging should never trigger fallback."""
    logger.info("test message")
    # If fallback is triggered, test fails with clear message
```

The fixture monkeypatches the fallback path (`serialize_mapping_to_json_bytes` in worker.py) to raise an error. This catches cases where:

- The envelope schema has drifted
- A new code path bypasses proper envelope construction
- Enrichers add incompatible data

### When to Use strict_serialization

- Integration tests that exercise the full logging pipeline
- Tests for new features that touch serialization
- Smoke tests for critical paths

### When NOT to Use strict_serialization

- Tests that deliberately exercise the fallback path
- Tests for error handling in serialization
- Tests with non-standard envelope structures

## Type Definitions

The schema is defined as TypedDicts in `src/fapilog/core/schema.py`:

```python
from fapilog.core.schema import LogEnvelopeV1, LogContext, LogDiagnostics
```

These types provide:

- **Static type checking**: mypy catches mismatches at lint time
- **IDE support**: autocomplete for schema fields
- **Documentation**: single source of truth for the schema

### Function Signatures

```python
def build_envelope(...) -> LogEnvelopeV1: ...
def serialize_envelope(log: Mapping[str, Any]) -> SerializedView: ...
```

The `build_envelope()` return type ensures it produces valid schema. The `serialize_envelope()` parameter remains `Mapping[str, Any]` for flexibility with enriched data.

## Contract Test Categories

| Category | Purpose | Example |
|----------|---------|---------|
| **Roundtrip** | Producer output → Consumer input | `serialize_envelope(build_envelope(...))` |
| **Schema** | Output validates against JSON schema | `jsonschema.validate(output, schema)` |
| **Type** | TypedDict matches runtime structure | Verify field types and presence |
| **Pipeline** | Full pipeline produces valid output | Logger → Worker → Sink |

## Detecting Schema Drift

Schema drift is detected when:

1. **Contract tests fail**: Roundtrip test raises an exception
2. **Schema validation fails**: Output doesn't match JSON schema
3. **Type check fails**: mypy reports type mismatch
4. **Fallback triggers**: strict_serialization fixture fails

### Investigation Steps

1. Check which test failed and the error message
2. Compare `build_envelope()` output with `serialize_envelope()` expectations
3. Review recent changes to either function
4. Verify the JSON schema matches the TypedDict definitions

## Best Practices

1. **Test real interfaces**: Use actual function output, not synthetic data
2. **Cover all options**: Test with various combinations of optional parameters
3. **Validate against schema**: Don't just check serialization succeeds
4. **Use strict mode in integration tests**: Catch fallback path usage
5. **Keep tests fast**: Contract tests should run in milliseconds
