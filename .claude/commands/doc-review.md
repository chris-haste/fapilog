---
name: doc-review
description: Review documentation for accuracy against code, feature coverage, quality, and redundancy. Report-only validation.
---

# Documentation Review

Validate that repository documentation is accurate, complete, consistent, and free from redundancy.

## Scope

**Include:**
- All markdown files (`.md`)
- Docstrings in source code
- Inline code comments that document behavior
- Configuration file comments
- API documentation

**Exclude:**
- `/docs/stories/` directory and all contents
- Markdown files with ALL-CAPS names (e.g., `CONTRIBUTING.md`, `LICENSE.md`, `CHANGELOG.md`), except `README.md` which should be included

## On Invoke

1. **Discover documentation standards** - Check for a documentation standards file in the repo (e.g., `docs/standards.md`, `DOCUMENTATION.md`, `.github/DOCUMENTATION_STANDARDS.md`, or similar). If found, load and enforce these standards throughout the review.

2. **Inventory documentation** - Identify all in-scope documentation files and locations.

3. **Inventory key features** - Scan the codebase to identify key features, public APIs, modules, and functionality that should be documented.

4. **Validate accuracy** - For each documented claim, verify it matches actual code behavior:
   - API signatures and parameters
   - Configuration options and defaults
   - Behavioral descriptions
   - Example code and usage patterns
   - Version compatibility claims
   - Dependencies and requirements

5. **Check coverage** - Ensure all key features are documented:
   - Public APIs and their parameters
   - Configuration options
   - Key workflows and processes
   - Error handling and edge cases
   - Setup and installation steps

6. **Assess quality** - Evaluate documentation for:
   - Clarity and readability
   - Consistency in terminology and style
   - Logical organization
   - Completeness of explanations
   - Usefulness to the target audience

7. **Identify redundancy** - Find documentation that is:
   - Duplicated across multiple locations
   - Superseded by newer documentation
   - Outdated and no longer relevant
   - Contradictory to other documentation

8. **Produce report** - Generate structured findings.

## Output Format

### Summary

| Category | Status | Issue Count |
|----------|--------|-------------|
| Accuracy | Verified / Issues Found | N |
| Coverage | Complete / Gaps Found | N |
| Quality | Good / Needs Work | N |
| Redundancy | Clean / Issues Found | N |

**Overall Assessment:** [PASS / NEEDS ATTENTION / CRITICAL ISSUES]

### Documentation Standards

If a documentation standards file was found:
> Enforcing standards from: `<path to standards file>`

If not found:
> No documentation standards file found. Using general best practices.

### Issues

#### P0 - Critical (Must Fix)
- False claims that could cause errors or security issues
- Dangerous misinformation
- Completely incorrect API documentation

#### P1 - Important (Should Fix)
- Inaccurate descriptions of behavior
- Missing documentation for key features
- Significant outdated information
- Contradictory documentation

#### P2 - Minor (Consider Fixing)
- Minor inaccuracies or imprecisions
- Documentation gaps for non-critical features
- Style inconsistencies
- Readability improvements
- Minor redundancies

### Detailed Findings

For each issue, report:

```
**[P0/P1/P2] <Category>: <Brief Description>**
- Location: `<file path>:<line number if applicable>`
- Problem: <What is wrong>
- Evidence: <Code reference or contradiction that proves the issue>
- Suggestion: <How to fix>
```

### Coverage Gap Summary

| Feature/API | Location in Code | Documentation Status |
|-------------|------------------|---------------------|
| `<feature>` | `<file:line>` | Missing / Incomplete / Documented |

### Redundancy Summary

| Document | Issue | Related To |
|----------|-------|------------|
| `<path>` | Duplicate / Superseded / Outdated | `<other doc or code change>` |

## Hard Rules

1. **Evidence-based only** - Every accuracy issue MUST reference specific code that contradicts the documentation. No speculative issues.

2. **No fixes** - This skill produces a report only. Do not modify any files.

3. **Respect scope** - Never report issues in excluded files (`/docs/stories/`, ALL-CAPS markdown files except `README.md`).

4. **Severity accuracy** - P0 is reserved for issues that could cause real harm (security, data loss, critical errors). Do not inflate severity.

5. **Feature significance** - When assessing coverage, focus on features users need to know about. Internal implementation details do not require documentation.

6. **Standards compliance** - If a documentation standards file exists, violations of those standards are P1 issues. If no standards file exists, style issues are P2 at most.

## What This Skill Does NOT Do

- Modify or fix documentation
- Review excluded files (stories, ALL-CAPS markdown except README.md)
- Report on code quality (only documentation quality)
- Generate new documentation
- Make subjective judgments without evidence
