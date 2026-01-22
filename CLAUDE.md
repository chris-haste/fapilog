# Fapilog - Project Conventions

## Development Workflow

```
implement → code-review → create-pr
```

1. **implement**: Implement with TDD (RED/GREEN/REFACTOR), commit, push
2. **code-review**: Review against story acceptance criteria
3. **create-pr**: Generate PR with pre-filled content from story

## Story Status Lifecycle

Stories in `docs/stories/` follow this status progression:

```
Draft → Ready → Ready for Code Review → Complete
```

- **Draft**: Initial creation, needs refinement
- **Ready**: Reviewed and approved for implementation
- **Ready for Code Review**: Implementation complete, awaiting review
- **Complete**: Merged to main

## Branch Naming

**Format:** `<type>/story-<id>-<title-slug>`

| Component    | Description                                  |
| ------------ | -------------------------------------------- |
| `type`       | feat, fix, refactor, chore, docs, test, perf |
| `id`         | Story number (e.g., 5.25)                    |
| `title-slug` | Kebab-case from story title, max ~30 chars   |

**Examples:**

- `feat/story-5.26-add-sink-routing`
- `fix/story-5.27-handle-null-logger`
- `refactor/story-5.25-extract-config-builders`

## Commit Message Format

```
<type>(<scope>): <message title>

- <bullet summarizing change>
- <bullet summarizing change>
```

**Types:** feat | fix | chore | docs | refactor | test | style | perf

**Rules:**

- Imperative mood, lowercase, no period
- Title max 50 chars
- Scope is optional but recommended
- Body bullets explain _why_, not just _what_
- No Co-Authored-By, "Generated with", or AI attribution lines

**Example:**

```
refactor(core): extract config builders from __init__.py

- Reduce __init__.py complexity by moving builder functions
- Enable independent testing of configuration logic
```

## PR Format

**Title:** `<type>(<scope>): <story title>`

**Rules:**

- No promotional banners or "Generated with" footers

**Body template:**

```markdown
## Summary

<First paragraph or description from story>

## Changes

- `path/to/file.py` (new|modified|deleted)

## Acceptance Criteria

- [x] <AC from story>

## Test Plan

- [x] Unit tests pass
- [x] Coverage >= 90%

## Story

[<id> - <title>](docs/stories/<story-file>.md)
```

## Scope Inference

Derive scope from primary directory of production code changes:

| Path                      | Scope                    |
| ------------------------- | ------------------------ |
| `src/fapilog/core/*`      | `core`                   |
| `src/fapilog/sinks/*`     | `sinks`                  |
| `src/fapilog/enrichers/*` | `enrichers`              |
| `src/fapilog/redactors/*` | `redactors`              |
| `src/fapilog/filters/*`   | `filters`                |
| `src/fapilog/*.py`        | `fapilog`                |
| Multiple directories      | most significant or omit |

## Quality Gates

Before committing, all changes must pass:

- **Tests**: `pytest` on changed test files
- **Linting**: `ruff check` + `ruff format --check`
- **Types**: `mypy` on changed files
- **Coverage**: 90% minimum on changed lines
- **Dead code**: `vulture src/ tests/`
- **Assertions**: `python scripts/lint_test_assertions.py tests/`

## Testing Principles

### Contract Tests (Producer/Consumer)

When a function's output is consumed by another function, test them together:

```python
# BAD: Testing serialize_envelope() with hand-crafted data
def test_serialize():
    data = {"timestamp": ..., "context": {}, "diagnostics": {}}  # Manual dict
    serialize_envelope(data)  # Passes, but real pipeline may fail!

# GOOD: Testing the actual contract
def test_serialize_accepts_real_envelope():
    envelope = build_envelope(level="INFO", message="test")  # Real output
    serialize_envelope(envelope)  # Tests the actual interface
```

**Rule:** If function A's output feeds function B, write a test that calls `B(A(...))`.

### Avoid Hand-Crafted Test Data for Internal Interfaces

- Use real functions to generate test data where possible
- If you must hand-craft data, ensure it matches what the real producer outputs
- Watch for tests that "work around" validation by adding fields manually

### Schema Drift Warning Signs

If you find yourself:
- Adding fields to test data to make a consumer function happy
- Writing comments like "this will fail because X doesn't have Y"
- Catching exceptions as "expected behavior" in normal code paths

**Stop.** These are signs of schema drift. The producer and consumer are misaligned.
