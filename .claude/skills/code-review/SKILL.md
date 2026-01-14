---
name: code-review
description: Use when reviewing code changes, checking staged files, or validating work against acceptance criteria. Triggers on requests to review changes, check work, or validate implementation.
---

# Code Review

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

## Review Steps

### 1. Load Context
- Read story file, extract: Status, Goals, Acceptance Criteria, DoD checklist
- `git branch --show-current`
- `git diff --cached --stat` then `git diff --cached`

### 2. Review Dimensions
- **Correctness**: edge cases, error handling, invariants
- **Maintainability**: readability, scope drift, unnecessary abstraction
- **Tests**: meaningful coverage vs padding, missing critical paths
- **Security**: secrets, injection, unsafe subprocess
- **Performance**: obvious hotspots, unnecessary IO

### 3. Classify Issues
- **P0**: Blocks merge (bugs, security holes, missing critical functionality)
- **P1**: Should fix before merge (test gaps, error handling, maintainability)
- **P2**: Consider fixing (style, minor improvements)

### 4. Test Check
- Detect test runner from repo (pytest, tox, etc.)
- Suggest minimal focused test command
- Use existing test output if available; never fabricate results

## Handling Precommit Changes

If user mentions precommit modified files:
1. Run `git diff` to see unstaged changes from hooks
2. Ask: "Precommit modified these files: [list]. Stage them for re-review?"
3. If yes: `git add [files]` and restart review

## Output

### If P0/P1/P2 Issues Exist

```
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
| Criterion | Status | Notes |
|-----------|--------|-------|
| [AC item] | Pass/Fail/partial | [details] |

### Test Gaps
- [Missing test scenarios]

### Verification Commands
[copy-paste commands to run]

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
All acceptance criteria met.

### Verification Commands
[Final test commands to run before PR]
```

Then:
1. Update the story's `**Status:**` field to `Complete`
2. Check off DoD items that are verified
3. Tell user: "Updated story status to Complete. Ready for /commit-pr"

## Style
- Concise, high-signal
- No fluff or pleasantries
- Link findings to specific files/lines
- Actionable recommendations only
