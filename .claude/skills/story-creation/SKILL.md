---
name: story-creation
description: Use when creating new stories, writing requirements, or drafting feature specifications. Triggers on requests to create stories, write specs, or plan new features.
---

# Story Creation

Stories live in `/docs/stories/`.

## When to Apply

- User asks to create a new story
- User asks to write a feature spec
- User wants to document requirements
- User mentions planning a new feature

## On Activation

Ask: "What feature or change would you like to create a story for?"

Wait for response, then gather:
1. Which series does this belong to? (Check existing stories for context)
2. What's the core problem being solved?
3. Any dependencies on other stories?

## Story Numbering Convention

Format: `{series}.{number}.{slug}.md`

**Existing series:**
- `1.x` - Core features (plugin contracts, schema versioning)
- `3.x` - Enterprise/compliance features
- `4.x` - Audit and security features
- `10.x` - Developer experience (DX) improvements

**To determine the next number:**
```bash
ls docs/stories/{series}.* | sort -V | tail -1
```

Increment from the highest number in that series.

## Story Template

Use the template in `references/template.md` as the starting point.

**Required sections:**
1. **Header** - Title, Status (Draft), Priority, Dependencies
2. **Context / Background** - Why this matters, current state
3. **Scope (In / Out)** - Clear boundaries
4. **Acceptance Criteria** - Specific, testable criteria
5. **Tasks** - Checkboxes for implementation
6. **Tests** - What tests are needed
7. **Definition of Done** - Quality checklist
8. **Risks / Rollback** - What could go wrong, how to recover

**Optional sections (add when relevant):**
- Implementation Notes - Code examples, file paths
- API Design Decision - When there are multiple approaches
- Related Stories - Dependencies and follow-ups

## Quality Guidelines

### Acceptance Criteria
- Each criterion must be testable (can verify pass/fail)
- Use concrete examples, not vague descriptions
- Include code snippets where helpful
- Number them (AC1, AC2...) for reference

### Scope Boundaries
- "In Scope" - What this story WILL do
- "Out of Scope" - What this story will NOT do (prevents scope creep)
- Be explicit about what's deferred to future stories

### Tasks
- Break into phases if complex (Phase 1: Core, Phase 2: Integration, etc.)
- Use checkboxes `- [ ]` for tracking
- Keep tasks small enough to complete in one session

### Context / Background
- Start with the problem, not the solution
- Reference existing code paths with file:line format
- Explain why existing solutions don't work

## Validation Before Saving

Before creating the story file:
1. Check the series number doesn't already exist
2. Verify dependencies reference real stories
3. Ensure acceptance criteria are testable
4. Confirm scope boundaries are clear

## Output

Create the story file at: `docs/stories/{series}.{number}.{slug}.md`

After creation, offer to run the story-review skill to validate.

## Style
- Concise but complete
- Use code blocks for examples
- Tables for comparisons/options
- Bullet points over paragraphs
- No fluff - every section should add value
