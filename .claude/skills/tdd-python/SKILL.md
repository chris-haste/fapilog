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
- `mypy <changed-files>` passes

Verify:
- Tests exist for new/changed behavior (or explicit exception below)
- Tests are meaningful, isolated, deterministic, and clearly named
- No secrets; inputs validated; errors not swallowed

Then stage: `git add <changed-files>`

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
