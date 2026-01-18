---
orphan: true
---

# Changelog Workflow

This document describes how changelog entries are generated and maintained in fapilog.

## Overview

Fapilog uses a semi-automated changelog workflow:

1. **Conventional Commits** - All commits must follow the [Conventional Commits](https://www.conventionalcommits.org/) format
2. **git-cliff** - Generates changelog entries from commit history
3. **Manual Review** - Generated entries are reviewed and curated before release
4. **Release Validation** - CI verifies changelog has entry for tagged version

## Commit Message Format

All commits must follow conventional commit format:

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Types

| Type       | Changelog Category | Description                          |
|------------|-------------------|--------------------------------------|
| `feat`     | Added             | New feature                          |
| `fix`      | Fixed             | Bug fix                              |
| `docs`     | Documentation     | Documentation changes                |
| `refactor` | Changed           | Code refactoring                     |
| `perf`     | Changed           | Performance improvements             |
| `style`    | Changed           | Code style changes (formatting)      |
| `test`     | (excluded)        | Adding or updating tests             |
| `chore`    | (excluded)        | Maintenance tasks                    |
| `ci`       | (excluded)        | CI/CD changes                        |

### Scopes (Optional)

Scope should reflect the primary area of change:

- `core` - Core logging functionality
- `sinks` - Log sinks
- `enrichers` - Log enrichers
- `redactors` - Log redactors
- `filters` - Log filters
- `plugins` - Plugin system
- `fastapi` - FastAPI integration
- `metrics` - Metrics/observability
- `testing` - Testing utilities
- `docs` - Documentation
- `ci` - CI/CD configuration
- `deps` - Dependencies

### Examples

```bash
# Feature with scope
git commit -m "feat(sinks): add Kafka sink support"

# Bug fix
git commit -m "fix(core): resolve queue overflow on high load"

# Documentation
git commit -m "docs: update installation instructions"

# Breaking change (note the !)
git commit -m "feat(core)!: change default batch size"
```

## Generating Changelog

### Prerequisites

Install git-cliff:

```bash
# macOS
brew install git-cliff

# Cargo (any platform)
cargo install git-cliff

# Or use without installing
npx git-cliff
```

### Generate Unreleased Changes

Preview what would be added to the changelog:

```bash
git-cliff --unreleased
```

### Generate Full Changelog

Regenerate the entire changelog from git history:

```bash
git-cliff -o CHANGELOG.md
```

### Generate Changelog for Specific Range

```bash
# Changes between tags
git-cliff v0.3.4..v0.3.5

# Changes since last tag
git-cliff --unreleased
```

## Pre-Release Workflow

Before tagging a release:

1. **Generate changelog preview**
   ```bash
   git-cliff --unreleased
   ```

2. **Move entries from [Unreleased] to version section**
   - Edit `CHANGELOG.md`
   - Create new version heading: `## [x.y.z] - YYYY-MM-DD`
   - Review and curate auto-generated entries
   - Add any manual entries missed by automation

3. **Commit changelog update**
   ```bash
   git add CHANGELOG.md
   git commit -m "docs: update changelog for vx.y.z"
   ```

4. **Create and push tag**
   ```bash
   git tag -a vx.y.z -m "Release vx.y.z"
   git push origin main --tags
   ```

## Release Validation

The release workflow validates:

1. **Changelog section exists** - `## [x.y.z]` heading must be present
2. **Section is not empty** - Must have content under the heading

If validation fails, the release workflow will abort with an error message.

## Enforcement

### Commit Message Linting

Commits are validated by `conventional-pre-commit`:

```bash
# Install hooks (first time)
pre-commit install --hook-type commit-msg

# Test locally
echo "invalid message" | pre-commit run conventional-pre-commit --hook-stage commit-msg
# Should fail

echo "feat: valid message" | pre-commit run conventional-pre-commit --hook-stage commit-msg
# Should pass
```

### What Happens on Invalid Commit

```
Conventional Commit.......................................................Failed
- hook id: conventional-pre-commit
- exit code: 1

[Bad commit message] >> "fixed a bug"
Your commit message does not follow Conventional Commits formatting.
https://www.conventionalcommits.org/

Expected format: <type>[(scope)]: <description>
Example: fix(core): resolve null pointer exception
```

## Configuration

### Commit Linting

Configuration in `.commitlintrc.yaml`:

- Allowed types (feat, fix, docs, etc.)
- Allowed scopes (core, sinks, etc.)
- Header length limits

### Changelog Generation

Configuration in `cliff.toml`:

- Commit type to category mapping
- Output format (Keep-a-Changelog)
- Excluded commit types
- Template customization

## FAQ

### Q: Can I bypass commit validation?

Use `--no-verify` only for exceptional cases:

```bash
git commit --no-verify -m "wip: temporary work in progress"
```

This should be avoided for commits that will be merged to main.

### Q: How do I fix a bad commit message?

Amend the most recent commit:

```bash
git commit --amend -m "feat(core): proper message"
```

For older commits, use interactive rebase (advanced).

### Q: What if auto-generated entries need editing?

The generated changelog is a starting point. Always review and edit:

- Improve descriptions for clarity
- Group related changes
- Add context where needed
- Remove noise (trivial changes)

### Q: What about commits before we adopted this?

Historical commits without conventional format are excluded from auto-generation. The existing CHANGELOG.md entries for older releases are manually maintained.
