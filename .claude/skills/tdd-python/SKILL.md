---
name: tdd-python
description: Use when implementing features, fixing bugs, writing new code, or making changes to Python files. Enforces red-green-refactor TDD workflow with tests-first approach.
---

# TDD Python (Lean + Enforced)

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
  - If diff-cover fails: identify *what behavior* is untested, then write tests for that behavior (not just to hit lines)
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

Do NOT commit or push - user must explicitly request /commit-pr for that.

Deferred to commit-pr/CI: full test suite, coverage, vulture

## Allowed Exceptions (Must Be Explicit + Safety Net Stated)

If invoking an exception, you MUST name it and state the safety net.

- Exploratory spike: throwaway code OR clearly marked for removal
- Legacy rescue: characterization / golden master tests first (see references/legacy-code.md)
- UI/visual-only: manual verification allowed, but business logic still tested

## Output Style

- Keep updates terse and action-oriented.
- Prefer bullets.
- Only expand when tests fail or risk is high.
