---
name: code-review
description: Use when reviewing code changes, checking staged files, or validating work against acceptance criteria. Triggers on requests to review changes, check work, or validate implementation.
version: 1.0.0
license: Apache-2.0
---

# Code Review

**Author:** Chris Haste
**GitHub:** https://github.com/chris-haste
**LinkedIn:** https://www.linkedin.com/in/chaste/
**Email:** chris@fapilog.dev

Tech Lead review of changes against story acceptance criteria.

## When to Apply

- User asks to review their changes
- User asks to check staged files
- User asks to validate work against a story
- User mentions they're done implementing and want feedback
- User asks if changes are ready for PR

## Status Indicator (Required)

Always output a status line at the start of your response:

**"📋 Starting code review..."**

This gives the user immediate visibility that the skill is active.

## Story Status Gate

**If reviewing against a story:** After loading the story, check the `**Status:**` field.

- If status is `Ready for Code Review` → proceed with review
- If status is NOT `Ready for Code Review` → **ABORT** and inform the user: "Story status is '{status}', expected 'Ready for Code Review'. Please ensure implementation is complete before code review."

## On Activation

1. Ask: "Which story should I review against?" (expect path like `docs/stories/story-10-5.md` or story number)
2. Check `git diff --cached --stat`
   - If no staged files: Check `git diff --stat` for unstaged changes
   - If files found: Confirm "I see these files: [list]. Ready to review?"
3. Wait for confirmation before proceeding.

## Hard Rules

- Review staged files only (`git diff --cached`) unless user specifies otherwise
- Read-only except: update story Status/checklists when no P0/P1/P2 issues
- Evidence-based: use diffs, file reads, test output - never fabricate
- Specific suggestions: file path + what to change conceptually (no patches)
- **Fresh perspective**: Review as if seeing the code for the first time. Never rely on memory of what was "intended" during implementation. For each AC, cite specific `file:line` evidence from the actual diff.

## Review Steps

### 1. Load Context

- Read story file, extract: Status, Goals, Acceptance Criteria, DoD checklist
- `git branch --show-current`
- `git diff --cached --stat` then `git diff --cached`

### 2. Review Dimensions

- **Correctness**: edge cases, error handling, invariants
- **Maintainability**: readability, scope drift, unnecessary abstraction
- **Tests**: meaningful coverage vs padding, missing critical paths, **no weak assertions**
  - Flag as P1: `assert True`, `assert result`, `assert result is not None`, `assert len(x) > 0`
  - Flag as P1: tests with no assertions, `assert isinstance()` alone, catching exceptions without asserting content
  - Require: `assert result == expected`, specific attribute checks, `pytest.raises(Error, match="pattern")`
- **Type Safety**: type annotations present, mypy passes
  - Flag as P1: missing type annotations on new functions/methods
  - Flag as P1: unresolved mypy errors or excessive `# type: ignore` usage
- **Security**: secrets, injection, unsafe subprocess
- **Performance**: obvious hotspots, unnecessary IO

### 3. AC Verification (Evidence-Required)

For EACH acceptance criterion from the story:

1. Identify which files/functions should implement it
2. Read the actual code in `git diff --cached` for those sections
3. Verify the code behavior matches the AC requirement
4. Document: `file:line` + brief explanation of how code satisfies AC
5. If no clear evidence in diff → mark as Fail or Partial

**Do NOT mark an AC as Pass based on:**

- Memory of what you implemented earlier in the conversation
- Assumption that it "should work" based on intent
- Test names alone (must verify test assertions actually validate the AC)
- Code that was written but not staged

### 4. Classify Issues

- **P0**: Blocks merge (bugs, security holes, missing critical functionality)
- **P1**: Should fix before merge (test gaps, error handling, maintainability)
- **P2**: Consider fixing (style, minor improvements)

### 5. Test Check

- Detect test runner from repo (pytest, tox, etc.)
- Suggest minimal focused test command
- Use existing test output if available; never fabricate results

### 6. DoD Verification

- Read the story's Definition of Done checklist
- Verify each item against the staged changes:
  - **Code Complete**: All AC implemented? Follows project patterns? No new linting errors?
  - **Quality Assurance**:
    - Tests written and passing?
    - `ruff check` and `ruff format --check` pass?
    - **Run `mypy <changed-files>`** - must pass with no errors
    - **Run `diff-cover coverage.xml --fail-under=90`** - changed lines must have coverage
    - **Run `python scripts/lint_test_assertions.py tests/`** - no weak assertions
    - **Run `vulture src/ tests/`** - no dead code
    - **Run `python scripts/check_pydantic_v1.py`** - no deprecated Pydantic v1 syntax
    - **Run `python scripts/check_settings_descriptions.py --min-length 15`** (if Settings touched)
  - **Documentation**: Docstrings where needed? README/CHANGELOG updated if required?
- Flag any unmet DoD items as P1 issues

## Handling Precommit Changes

If user mentions precommit modified files:

1. Run `git diff` to see unstaged changes from hooks
2. Ask: "Precommit modified these files: [list]. Stage them for re-review?"
3. If yes: `git add [files]` and restart review

## Output

### If P0/P1/P2 Issues Exist

````
## Review: [Story Number]

### Summary
[1-2 sentences on what the changes do]

### What's Good
- [Positive findings]

### Issues

#### P0 (Blockers)
- [issue]: [file:line] - [what's wrong, why it matters]

#### P1 (Should Fix)
- [issue]: [file:line] - [what's wrong, suggested fix]

#### P2 (Consider)
- [issue]: [file:line] - [suggestion]

### AC Coverage
| Criterion | Status | Evidence |
|-----------|--------|----------|
| [AC item] | Pass/Fail/Partial | `file:line` - [how code satisfies AC, or why it fails] |

### DoD Status
| Item | Status | Notes |
|------|--------|-------|
| [DoD item] | Pass/Fail | [details] |

### Test Gaps
- [Missing test scenarios]

### Verification Commands
```bash
# Run these before PR:
ruff check <changed-files>
ruff format --check <changed-files>
mypy <changed-files>
pytest --cov=src/fapilog --cov-report=xml && diff-cover coverage.xml --fail-under=90
python scripts/lint_test_assertions.py tests/
vulture src/ tests/
python scripts/check_pydantic_v1.py
python scripts/check_settings_descriptions.py --min-length 15
````

### Next Steps

1. [Ordered, actionable items]

```

### If No P0/P1/P2 Issues

```

## Review: [Story Number]

**OK to PR**

### Summary

[What was implemented]

### What's Good

- [Key positives]

### AC Coverage
| Criterion | Status | Evidence |
|-----------|--------|----------|
| [AC item] | Pass | `file:line` - [how code satisfies AC] |

### DoD Status

All Definition of Done items verified.

### Verification Commands

```bash
# Final checks before PR:
ruff check <changed-files>
mypy <changed-files>
pytest --cov=src/fapilog --cov-report=xml && diff-cover coverage.xml --fail-under=90
python scripts/lint_test_assertions.py tests/
vulture src/ tests/
python scripts/check_pydantic_v1.py
python scripts/check_settings_descriptions.py --min-length 15
```

```

Then:
1. Update the story's `**Status:**` field to `Complete`
2. Check off DoD items that are verified
3. Append a **Code Review** section to the story (see format below)
4. Tell user: "Updated story status to Complete. Ready for /create-pr"

## Story Update: Code Review Section

After a successful review (no P0/P1/P2 issues), append this section to the story file before the Change Log:

```markdown
---

## Code Review

**Date:** YYYY-MM-DD
**Reviewer:** Claude
**Verdict:** OK to PR

### Summary

[1-2 sentences describing what was reviewed]

### AC Verification

| Criterion | Evidence |
|-----------|----------|
| [AC item] | `file:line` - [how code satisfies AC] |

### Quality Gates

- [x] ruff check passed
- [x] ruff format passed
- [x] mypy passed
- [x] diff-cover >= 90%
- [x] No weak assertions
- [x] No dead code
```

If issues were found and fixed, include a subsection noting them:

```markdown
### Issues Addressed

- [P1/P2] [Brief description] - Fixed in [file:line]
```

## Style

- Concise, high-signal
- No fluff or pleasantries
- Link findings to specific files/lines
- Actionable recommendations only
