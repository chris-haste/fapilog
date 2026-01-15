---
name: create-pr
description: Generate a GitHub PR URL with pre-filled title and body from story metadata and changed files. Run after code-review passes.
version: 1.0.0
license: Apache-2.0
---

# Create PR

Generate a GitHub Pull Request URL with pre-filled title and body, derived from the story document and changed files.

**Author:** Chris Haste
**GitHub:** https://github.com/chris-haste

## When to Apply

- User explicitly requests `/create-pr`
- After `tdd-python` implementation is complete
- After `code-review` has passed

## Prerequisites

- Implementation committed and pushed (via `tdd-python`)
- Code review passed (via `code-review`)
- On a feature branch with format: `<type>/story-<id>-<title-slug>`

## Workflow

### 1. Gather Context

**From branch name:**
- Parse type, story ID from branch: `<type>/story-<id>-<slug>`
- Example: `refactor/story-5.25-extract-config-builders` → type=refactor, id=5.25

**From story file:**
- Locate story: `docs/stories/<id>.*.md`
- Extract: title, description/summary, acceptance criteria, test plan (if any)

**From git:**
- Get list of changed files vs base branch: `git diff --name-status main...HEAD`
- Get remote URL: `git remote get-url origin`
- Parse owner/repo from remote URL

### 2. Generate PR Title

Format: `<type>(<scope>): <story title>`

- `type`: From branch name (feat, fix, refactor, etc.)
- `scope`: Infer from primary directory of changes (e.g., `core`, `sinks`, `api`)
- `title`: From story document, lowercase, imperative mood

Example: `refactor(core): extract config builders from __init__.py`

### 3. Generate PR Body

Use this template:

```markdown
## Summary
<First paragraph or description from story>

## Changes
<List of files changed, grouped and annotated>
- `src/fapilog/core/config_builders.py` (new)
- `src/fapilog/__init__.py` (modified)
- `tests/unit/core/test_config_builders.py` (new)

## Acceptance Criteria
<From story, as checked items since code-review passed>
- [x] <AC 1>
- [x] <AC 2>
- [x] <AC 3>

## Test Plan
- [x] Unit tests pass
- [x] Coverage >= 90%
<Additional items from story test plan if any>

## Story
[<id> - <title>](docs/stories/<story-file>.md)
```

### 4. Generate GitHub URL

Build URL with query parameters:

```
https://github.com/<owner>/<repo>/compare/main...<branch>?expand=1&title=<url-encoded-title>&body=<url-encoded-body>
```

- URL-encode title and body properly
- Use `encodeURIComponent` equivalent encoding

### 5. Output

Display:

```
PR ready to create:

Title: <type>(<scope>): <story title>

Body:
## Summary
...

URL (click to open with pre-filled content):
<full-url>
```

## File Change Annotations

When listing changed files, annotate them:
- `(new)` - Added files (A in git status)
- `(modified)` - Changed files (M in git status)
- `(deleted)` - Removed files (D in git status)
- `(renamed)` - Renamed files (R in git status)

## Scope Inference

Infer scope from the primary directory of production code changes:
- `src/fapilog/core/*` → `core`
- `src/fapilog/sinks/*` → `sinks`
- `src/fapilog/enrichers/*` → `enrichers`
- `src/fapilog/*.py` → `fapilog`
- Multiple directories → use most significant or omit scope

## Error Handling

**If branch doesn't match expected format:**
- Warn user but attempt to continue
- Ask for story ID if not parseable

**If story file not found:**
- List available stories in `docs/stories/`
- Ask user to specify

**If not on a feature branch:**
- Abort: "Not on a feature branch. Please run from your implementation branch."

## What NOT To Do

- Do not actually create the PR (no `gh` CLI dependency)
- Do not modify any files
- Do not commit or push
- Do not guess story content if file not found
