---
name: story-review
description: Use when reviewing, validating, or checking story documents. Triggers on requests to review stories, validate requirements, or check story readiness.
---

# Story Review

Stories live in `/docs/stories/`.

## When to Apply

- User asks to review a story
- User asks to validate requirements
- User asks if a story is ready for implementation
- User mentions checking story completeness or accuracy

## On Activation

Ask: "Which story would you like me to review?"

Wait for response before proceeding.

## Review Dimensions

### 1. Need
- Problem well-defined? Real user need?
- Already solved by existing features? Search codebase to verify.
- Clear value proposition?

### 2. Accuracy
- Code examples match actual APIs/patterns?
- File paths, function names, config options correct?
- Dependencies correctly identified?
- Scope boundaries clear? Overlap with other stories?

### 3. Completeness
- Acceptance criteria specific and testable?
- Edge cases and error handling documented?
- Implementation guide sufficient?

### 4. Relationships
- Dependencies exist and have correct status?
- Fits epic/series context?

## Output Format

### Overall Assessment
- **Need**: Valid / Questionable / Not Needed
- **Accuracy**: Accurate / Needs Work / Inaccurate
- **Completeness**: Complete / Needs Expansion
- **Recommendation**: Approve / Revise / Reject

### Findings
- **Correct**: [what's right]
- **Issues**: [inaccuracies, missing items]
- **Must Fix**: [blockers]
- **Should Consider**: [improvements]

### Codebase Verification
List what was checked and findings.

## Style
- Direct, specific, actionable
- Reference sections/lines when citing issues
- Show correct vs incorrect code when relevant
