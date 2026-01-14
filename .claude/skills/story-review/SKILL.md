---
name: story-review
description: Use when reviewing, validating, or checking story documents. Triggers on requests to review stories, validate requirements, or check story readiness.
version: 1.0.0
license: Apache-2.0
---

# Story Review

**Author:** Chris Haste
**GitHub:** https://github.com/chris-haste
**LinkedIn:** https://www.linkedin.com/in/chaste/

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

## Status Updates

After completing the review:

1. **If Recommendation is "Approve"** and the story is valid:
   - Update the story's `**Status:**` field to `Ready`
   - This indicates the story is ready for implementation
   - Only update if the story was previously in `Draft` or similar non-ready status

2. **If issues were found and corrected** during the review:
   - After corrections are made and the story is validated, update `**Status:**` to `Ready`
   - Confirm the story is still valid before updating

3. **If Recommendation is "Reject"**:
   - Do NOT update to Ready
   - Consider updating `**Status:**` to `Cancelled` if appropriate

4. **Status format**: The status field is `**Status:** {value}` at the top of the story (e.g., `**Status:** Ready`)

**Note**: The "Ready" status means the story has been reviewed, is accurate, complete, and ready to start implementation. Dependencies should be met and design should be complete.

## Style
- Direct, specific, actionable
- Reference sections/lines when citing issues
- Show correct vs incorrect code when relevant
- Update story status when appropriate (see Status Updates section)
