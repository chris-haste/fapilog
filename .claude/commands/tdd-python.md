---
name: tdd-python
description: Enforced TDD for Python changes (red-green-refactor). Tests-first with mandatory run gates, boundary-only mocking, and explicit legacy/spike exceptions.
---

# TDD Python (Lean + Enforced)

## Non-negotiable gates

- No production code without a failing test that demands it (RED first).
- After each step: run focused tests and keep GREEN before continuing.
- Behavior change without relevant tests updated/added => STOP and add tests.
- No skipped/disabled tests unless an explicit exception applies.

## Default loop (repeat per smallest behavior)

1. RED: write/adjust the next smallest test
2. Run focused tests => must FAIL for the right reason
3. GREEN: minimal code to pass
4. Run focused tests => must PASS
5. REFACTOR: small cleanup only while GREEN
6. Run focused tests again => must PASS

## What "tests-first" means in practice

- Start from story intent / AC (if provided) and derive the next smallest observable behavior.
- Tests must assert behavior (inputs→outputs / side-effects), not private internals.
- Bug fix => add a regression test that would fail pre-fix.

## Mocking rule (boundary-only)

Mock only I/O boundaries (network, filesystem, time, external services, DB unless deliberately integration-testing the DB layer).
Avoid over-mocking internal collaborators.

## Edge cases (only when relevant)

Cover the meaningful boundaries for the changed behavior:

- empty/None inputs
- invalid inputs / error paths
- boundary values
- timezones/idempotency/concurrency only if the story touches them

## Reference files (use only when needed)

- For common test patterns (parametrize, async, tmp_path, caplog, monkeypatch, hypothesis):
  - references/patterns.md
- For legacy rescue / characterization / golden master / seams:
  - references/legacy-code.md

Do NOT paste large templates from references unless it directly solves the current task.

## "Done" gate (before final response / before staging completion)

- Tests exist for new/changed behavior (or explicit exception below)
- Focused tests pass (and full suite if DoD/risk requires)
- Tests are meaningful, isolated, deterministic, and clearly named
- Refactor step completed while green (no leftover mess)
- No secrets; inputs validated; errors not swallowed; repo conventions followed
- If story contains a DoD section: all DoD items verified complete

## Allowed exceptions (must be explicit + safety net stated)

If invoking an exception, you MUST name it and state the safety net.

- Exploratory spike: throwaway code OR clearly marked for removal
- Legacy rescue: characterization / golden master tests first (see references/legacy-code.md)
- UI/visual-only: manual verification allowed, but business logic still tested

## Output style

- Keep updates terse and action-oriented.
- Prefer bullets.
- Only expand when tests fail or risk is high.
