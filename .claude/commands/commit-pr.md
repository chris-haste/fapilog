---
name: commit-pr
description: Commit staged changes, handle precommit iterations, push, and create PR. Auto-restages precommit modifications but never stages new files without permission.
---

# Commit and PR

Commit staged changes, iterate through precommit checks, push, and create PR.

## Prerequisites

Files should be staged after passing focused tests + ruff + mypy (handled by tdd-python skill).

This command runs the full precommit suite which adds:
- Full test suite (via coverage-check)
- Coverage enforcement (90%+)
- Vulture (dead code)
- Other project guardrails

If precommit fails here, it's likely a regression or integration issue not caught by focused tests.

## On Invoke

1. Run `git status` to check staged files
   - If nothing staged: "No files staged. Please stage files and try again."
   - If staged: Show list and ask "Ready to commit these files?"
2. Wait for confirmation.

## Hard Rules

- **Never stage new files** without explicit permission
- **Auto-restage allowed** only for files modified by precommit hooks
- **Coverage failures**: Ask before adding tests—no test padding
- **No ads** in commit messages (no "Generated with..." footers)
- **Read staged files only** for commit message context

## Commit Message Format

```
<type>(<scope>): <message title>

- <bullet summarizing change>
- <bullet summarizing change>
```

**Types**: feat | fix | chore | docs | refactor | test | style | perf

**Rules**:
- Imperative mood, lowercase, no period, max 50 chars
- Scope optional but recommended
- Body bullets explain *why*, not just *what*

## Workflow

### 1. Pre-check
```bash
git status --porcelain=v1
git diff --cached --stat
```

### 2. Generate Commit Message
- Read staged diffs for context
- Draft message following format above
- Show user and ask for approval/edits

### 3. Attempt Commit
```bash
git commit -m "<message>"
```

### 4. Handle Precommit Results

**If commit succeeds**: Proceed to push.

**If precommit modifies files** (formatting, imports, etc.):
1. Run `git status` to identify modified files
2. Show: "Precommit modified: [files]. Restaging and retrying."
3. `git add <modified files>` (only files that were already staged)
4. Retry commit
5. Max 3 iterations, then ask user for help

**If precommit fails** (lint errors, type errors):
1. Show the error output
2. Ask: "Fix these issues?"
3. If yes: fix, but only restage files that were originally staged
4. Retry commit

**If tests/coverage fail**:
1. Show failure output
2. Ask: "Tests failed. Want me to investigate and suggest fixes?"
3. Never auto-add tests—always ask first
4. If adding tests: explain what's missing, get approval, then add

### 5. Push
```bash
git push -u origin <branch>
```

If push fails (network): retry up to 4x with exponential backoff (2s, 4s, 8s, 16s).

### 6. Create PR

Check for `gh` CLI:
```bash
gh pr create --title "<type>(<scope>): <title>" --body "$(cat <<'EOF'
## Summary
- <bullets from commit>

## Test Plan
- [ ] <verification steps>
EOF
)"
```

If `gh` unavailable: provide GitHub PR URL.

## Output

On success:
```
Committed: <hash> <message>
Pushed to: origin/<branch>
PR: <url>
```

On failure at any step: show error, ask how to proceed.

## Iteration Example

```
→ git commit -m "feat(api): add user endpoint"
→ [precommit runs black, modifies 2 files]
→ "Precommit reformatted: src/api.py, src/models.py. Restaging..."
→ git add src/api.py src/models.py
→ git commit -m "feat(api): add user endpoint"
→ [commit succeeds]
→ git push -u origin feature/user-endpoint
→ gh pr create ...
→ "PR created: https://github.com/..."
```

## What NOT To Do

- Stage files not originally staged
- Add tests without asking
- Retry indefinitely on failures
- Use vague commit messages ("update", "fix stuff")
- Mix unrelated changes in one commit
