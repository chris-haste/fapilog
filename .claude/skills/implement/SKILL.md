---
name: implement
description: Use when implementing features, fixing bugs, writing new code, or making changes to Python files. Manages branch creation, TDD workflow, quality gates, and commit/push.
version: 1.0.0
license: Apache-2.0
---

# Implement (Python)

**Author:** Chris Haste
**GitHub:** https://github.com/chris-haste
**LinkedIn:** https://www.linkedin.com/in/chaste/
**Email:** chris@fapilog.dev

## When to Apply

- User asks to implement a story or feature
- User asks to fix a bug
- User asks to add functionality
- User asks to write or change Python code
- Any request that will result in production code changes

## Status Indicator (Required)

Always output a status line at the start of your response:

- If TDD applies: **"🧪 Starting TDD workflow..."**
- If TDD does not apply: **"ℹ️ TDD not applicable for this request"**

This gives the user immediate visibility into whether the skill is active.

## Story Readiness Gate

**If implementing a story:** Before starting, check the story's `**Status:**` field.

- If status is `Ready` → proceed with implementation
- If status is NOT `Ready` → **ABORT** and inform the user: "Story status is '{status}', expected 'Ready'. Please ensure the story has been reviewed before implementation."

## Branch Creation (Story Implementation)

**If implementing a story:** Create a feature branch before writing any code.

See `CLAUDE.md` for branch naming format: `<type>/story-<id>-<title-slug>`

**Steps:**

1. Parse story file for type (from title prefix or content) and title
2. Generate branch name per CLAUDE.md conventions
3. `git checkout -b <branch-name>`
4. Inform user: "Created branch: `<branch-name>`"

## Non-negotiable Gates

- No production code without a failing test that demands it (RED first).
- After each step: run focused tests and keep GREEN before continuing.
- Behavior change without relevant tests updated/added => STOP and add tests.
- No skipped/disabled tests unless an explicit exception applies.

## Default Loop (repeat per smallest behavior)

1. RED: write/adjust the next smallest test
2. Run focused tests => must FAIL for the right reason
3. GREEN: minimal code to pass
4. Run focused tests => must PASS
5. REFACTOR: small cleanup only while GREEN
   - Run `ruff check --fix <changed-files>` and `ruff format <changed-files>`
6. Run focused tests again => must PASS

## What "Tests-First" Means in Practice

- Start from story intent / AC (if provided) and derive the next smallest observable behavior.
- Tests must assert behavior (inputs->outputs / side-effects), not private internals.
- Bug fix => add a regression test that would fail pre-fix.

## Mocking Rule (Boundary-Only)

Mock only I/O boundaries (network, filesystem, time, external services, DB unless deliberately integration-testing the DB layer).
Avoid over-mocking internal collaborators.

## Test Assertion Quality (No Weak Assertions)

Every test must have meaningful assertions that verify specific behavior. Avoid weak assertions that pass trivially or don't validate actual outcomes.

**Prohibited patterns (weak assertions):**

- `assert True` / `assert False` - no actual verification
- `assert result` / `assert result is not None` - only checks existence, not correctness
- `assert len(x) > 0` - doesn't verify content
- `assert isinstance(x, SomeType)` alone - type checks aren't behavior tests
- Tests with no assertions at all
- `assert x == x` or other tautologies
- Catching exceptions without asserting on their content

**Required patterns (strong assertions):**

- `assert result == expected_value` - verify exact outcomes
- `assert result.field == "specific_value"` - verify specific attributes
- `assert len(items) == 3` - verify exact counts when count matters
- `assert "expected_substring" in error.message` - verify error details
- `pytest.raises(SpecificError, match="pattern")` - verify exception type AND message

**During RED phase:** Write assertions that will meaningfully fail. If a test can't fail for the right reason, the assertion is too weak.

## Edge Cases (Only When Relevant)

Cover the meaningful boundaries for the changed behavior:

- empty/None inputs
- invalid inputs / error paths
- boundary values
- timezones/idempotency/concurrency only if the story touches them

## Configuration Parity Rule

**Reference:** Stories 10.22-10.28, `docs/architecture/builder-design-patterns.md`

When adding or modifying any configuration in fapilog, follow the appropriate pattern based on category:

### Configuration Categories

| Category | Settings Location | Builder Pattern | Example |
|----------|-------------------|-----------------|---------|
| Core | `CoreSettings` | `with_*()` | `with_workers()` |
| Cloud Sinks | `CloudWatch/Loki/PostgresSinkSettings` | `add_*()` | `add_cloudwatch()` |
| Filters | `FilterConfig.*` | `with_*()` | `with_sampling()` |
| Processors | `ProcessorConfigSettings.*` | `with_*()` | `with_size_guard()` |
| Advanced | `SinkRoutingSettings`, `RedactorConfig.*` | `with_*()` | `with_routing()` |

### Required Steps (All Categories)

1. **Settings**: Add field to appropriate Settings class with docstring
2. **Builder**: Add/update corresponding builder method
3. **Mapping**: Update `scripts/builder_param_mappings.py`
4. **Test**: Add unit test for builder method
5. **Verify**: Run `python scripts/check_builder_parity.py`

### Category-Specific Patterns

#### Core Settings (`with_*` methods)

```python
# CoreSettings field
worker_count: int = Field(default=1, description="Number of workers")

# Builder method
def with_workers(self, count: int = 1) -> LoggerBuilder:
    self._config.setdefault("core", {})["worker_count"] = count
    return self
```

#### Cloud Sinks (`add_*` methods)

```python
# CloudWatchSinkSettings field
log_group_name: str = Field(...)

# Builder method parameter (note: simplified param name)
def add_cloudwatch(self, log_group: str, ...) -> LoggerBuilder:
    config["log_group_name"] = log_group  # Maps param -> field
```

**Param naming:** Use human-friendly names, document mapping in `builder_param_mappings.py`

#### Filters/Processors

```python
# with_sampling() enables 'sampling' filter AND configures it
def with_sampling(self, rate: float = 1.0, *, seed: int | None = None):
    filters = self._config.setdefault("core", {}).setdefault("filters", [])
    if "sampling" not in filters:
        filters.append("sampling")
    filter_config = self._config.setdefault("filter_config", {})
    filter_config["sampling"] = {"sample_rate": rate, "seed": seed}
```

### Consistency Requirements

- **Duration fields**: Accept both strings ("30s") and floats via `_parse_duration()`
- **Size fields**: Accept both strings ("10 MB") and ints
- **Boolean fields**: Use `enabled` as parameter name
- **Return type**: Always `Self` for chaining

### Checklist Before Complete

- [ ] Settings field added with description
- [ ] Builder method added with docstring and example
- [ ] Parameter mapping added to `scripts/builder_param_mappings.py`
- [ ] Unit test for builder method
- [ ] Parity test passes: `python scripts/check_builder_parity.py`

## Reference Files

For common test patterns and legacy code techniques, see:

- `references/patterns.md` - parametrize, async, tmp_path, caplog, monkeypatch, hypothesis
- `references/legacy-code.md` - characterization, golden master, seams

Do NOT paste large templates from references unless it directly solves the current task.

## "Done" Gate (Before Staging)

Quality checks on changed files:

- Focused tests pass
- `ruff check` + `ruff format --check` pass
- **Type checking**: `mypy <changed-files>` passes with no errors
  - All new functions/methods must have type annotations (parameters and return types)
  - Fix any type errors before staging (don't ignore with `# type: ignore` unless unavoidable)
  - If mypy reports errors, resolve them before proceeding
- **Coverage on changed lines**: `pytest --cov=src/fapilog --cov-report=xml && diff-cover coverage.xml --fail-under=90`
  - Changed/new lines must have test coverage
  - If diff-cover fails: identify _what behavior_ is untested, then write tests for that behavior (not just to hit lines)
  - Never write tests solely to satisfy coverage - if code can't be meaningfully tested, question whether it's needed
  - Full 90% minimum enforced by CI pipeline
- **Dead code**: `vulture src/ tests/` - no unused code
- **Pydantic v2 only**: `python scripts/check_pydantic_v1.py` - no deprecated v1 syntax
- **Settings descriptions**: `python scripts/check_settings_descriptions.py --min-length 15` (if touching Settings classes)

Verify:

- Tests exist for new/changed behavior (or explicit exception below)
- Tests are meaningful, isolated, deterministic, and clearly named
- **No weak assertions**: `python scripts/lint_test_assertions.py tests/` must pass
  - See "Test Assertion Quality" section for prohibited/required patterns
- No secrets; inputs validated; errors not swallowed

Then stage: `git add <changed-files>`

**If implementing a story:** Update the story's `**Status:**` field to `Ready for Code Review`.

## Commit and Push (After Done Gate)

After all quality checks pass and files are staged, prompt for commit:

**Ask:** "Implementation complete. OK to commit?"

**If user confirms:**

1. Generate commit message following format in `CLAUDE.md`

2. Show message and ask for approval/edits

3. Attempt commit: `git commit -m "<message>"`

4. **Handle precommit results:**

   - If precommit modifies files: restage modified files (only those originally staged), retry commit (max 3 iterations)
   - If precommit fails: show error, ask to fix, retry
   - If tests/coverage fail: show output, ask before adding tests

5. Push: `git push -u origin <branch>`
   - If push fails (network): retry up to 4x with exponential backoff (2s, 4s, 8s, 16s)

**Output on success:**

```
Committed: <hash> <message>
Pushed to: origin/<branch>
```

**Next step:** User runs `/code-review`, then `/create-pr` after review passes.

## Allowed Exceptions (Must Be Explicit + Safety Net Stated)

If invoking an exception, you MUST name it and state the safety net.

- Exploratory spike: throwaway code OR clearly marked for removal
- Legacy rescue: characterization / golden master tests first (see references/legacy-code.md)
- UI/visual-only: manual verification allowed, but business logic still tested

## Output Style

- Keep updates terse and action-oriented.
- Prefer bullets.
- Only expand when tests fail or risk is high.
