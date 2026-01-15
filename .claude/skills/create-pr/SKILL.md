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
- On a feature branch (see `CLAUDE.md` for branch naming format)

## Workflow

### 1. Gather Context

**From branch name:**
- Parse type, story ID from branch per `CLAUDE.md` format
- Example: `refactor/story-5.25-extract-config-builders` → type=refactor, id=5.25

**From story file:**
- Locate story: `docs/stories/<id>.*.md`
- Extract: title, description/summary, acceptance criteria, test plan (if any)

**From git:**
- Get list of changed files vs base branch: `git diff --name-status main...HEAD`
- Get remote URL: `git remote get-url origin`
- Parse owner/repo from remote URL

### 2. Generate PR Title

Use format from `CLAUDE.md`: `<type>(<scope>): <story title>`

- `type`: From branch name
- `scope`: Infer per `CLAUDE.md` scope rules
- `title`: From story document, lowercase, imperative mood

### 3. Generate PR Body

Use PR body template from `CLAUDE.md`, populated with:
- Summary from story description
- Changed files list with annotations
- Acceptance criteria (checked, since code-review passed)
- Test plan items
- Link to story document

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
