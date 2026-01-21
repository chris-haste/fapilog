# Builder API Generation Decision

This document evaluates whether to generate builder methods from the Settings schema or implement them manually.

## Decision

**Recommendation: Manual implementation with automated parity testing**

## Evaluation Summary

| Approach | Pros | Cons |
|----------|------|------|
| Code Generation | Guaranteed parity, less boilerplate | Complex transforms, limited customization |
| Manual + Parity Tests | Full control, better DX, clear intent | More code to write, risk of drift |

## Analysis

### Option 1: Schema-Driven Generation

Generate builder methods automatically from Pydantic model schemas.

**How it would work:**
1. Parse `CoreSettings.model_fields` and extract field metadata
2. Generate `with_*` methods for each field
3. Map Pydantic types to appropriate Python parameter types
4. Run generator as part of build or pre-commit

**Pros:**
- Guaranteed 1:1 parity with Settings
- New Settings fields automatically get builder methods
- No manual maintenance required
- Catches drift at generation time

**Cons:**
- **Complex transformations required:**
  - Nested settings (SinkConfig, SecuritySettings) need special handling
  - List fields (enrichers, sinks) need accumulation semantics
  - Human-readable string parsing needs custom logic per field type
- **Poor ergonomics:**
  - Generated method signatures may be awkward
  - No semantic grouping (e.g., circuit breaker fields split across methods)
  - Docstrings require manual templates or AI generation
- **Maintenance burden:**
  - Generator code becomes its own codebase to maintain
  - Edge cases accumulate over time
  - Debugging generated code is harder than manual code
- **Limited customization:**
  - Special methods like `add_cloudwatch()` need different parameters than raw Settings
  - Convenience methods (`add_stdout_pretty`) won't be generated

### Option 2: Manual Implementation + Parity Tests

Write builder methods by hand, with automated tests to detect drift.

**How it would work:**
1. Implement builder methods following design patterns document
2. Maintain mapping in `test_builder_parity.py`
3. Parity tests fail when new Settings fields lack coverage
4. Excluded fields documented explicitly

**Pros:**
- **Better developer experience:**
  - Methods designed for human ergonomics, not 1:1 field mapping
  - Logical grouping (e.g., `with_circuit_breaker(enabled, threshold, timeout)`)
  - Convenience methods where appropriate
- **Clear intent:**
  - Each method is purpose-built
  - Docstrings written for users, not generated
  - Examples reflect real usage patterns
- **Simpler codebase:**
  - No generator to maintain
  - Standard Python code, easy to debug
  - Changes are explicit and reviewable
- **Flexibility:**
  - Can deviate from Settings when it improves DX
  - Can add validation that Settings doesn't have
  - Can deprecate or alias fields

**Cons:**
- More code to write initially
- Risk of missing new Settings fields (mitigated by parity tests)
- Requires discipline to update mapping

## Decision Rationale

### Why Manual Implementation

1. **DX > Parity**: The goal is excellent developer experience, not perfect 1:1 mapping. Generated code optimizes for the latter.

2. **Semantic grouping matters**: Users think in concepts (circuit breakers, batching, routing), not individual fields. Manual methods can group related settings.

3. **Human-readable input requires custom logic**: Each field type (duration, size, enum) needs parsing. This logic is better expressed explicitly.

4. **Maintenance cost is acceptable**: With ~50 fields to cover across stories 10.23-10.26, manual implementation is a bounded effort. Generator maintenance would be ongoing.

5. **Parity tests catch drift**: The `test_builder_parity.py` infrastructure ensures coverage without requiring generation.

### Why Not Generation

1. **Complexity explosion**: Supporting nested configs, special types, and accumulation semantics would make the generator as complex as the manual code.

2. **One-size-fits-all doesn't fit**: CloudWatch sink needs `log_group` and `region`, not raw Settings field names. Generation can't optimize for this.

3. **Documentation quality**: Generated docstrings are either templates (poor) or require AI (unpredictable). Manual docs are better.

## Implementation Checklist for Manual Approach

When implementing new builder methods:

1. **Follow design patterns** (see `builder-design-patterns.md`)
2. **Update parity test mapping** in `test_builder_parity.py`
3. **Add unit tests** for the new method
4. **Update gap audit** in `builder-api-gaps.md` (mark as covered)

## Parity Test Infrastructure

The parity test infrastructure (`tests/test_builder_parity.py`) provides:

- `get_core_settings_fields()` - Extract all CoreSettings field names
- `get_sink_config_types()` - Extract all sink types
- `BUILDER_TO_CORE_FIELDS` - Mapping of builder methods to fields they cover
- `EXCLUDED_CORE_FIELDS` - Fields intentionally without builder coverage
- `test_all_core_settings_have_builder_coverage()` - Fails when gaps exist

Tests are marked `xfail` until stories 10.23-10.26 complete. Remove `xfail` markers as coverage improves.

## Future Considerations

If the Settings schema grows significantly (100+ fields), reconsider generation for:
- Bulk/boilerplate methods that don't need customization
- Type stubs or IDE completion hints
- Validation of parameter types against Settings

For now, manual implementation with parity testing is the right balance.
