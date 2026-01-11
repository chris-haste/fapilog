# Stories Directory

This directory contains detailed technical specifications and implementation plans for fapilog features and improvements. These are **internal planning documents** used by maintainers for roadmap planning and implementation.

## What Are Stories?

Stories are detailed technical specifications that include:
- **Context/Background**: Why this work is needed
- **Scope**: What's in and out of scope
- **Acceptance Criteria**: Clear conditions for completion
- **Technical Tasks**: Implementation steps
- **Testing Strategy**: How to validate the work
- **Definition of Done**: Comprehensive checklist for completion (REQUIRED)

## Story Naming Convention

Stories follow this naming pattern:
```
{series}.{number}.{kebab-case-name}.md
```

Examples:
- `10.0-series-overview.md` - Epic/Series overview
- `10.1.configuration-presets.md` - Individual story
- `4.15.integrity-enricher-chain-state.md` - Technical story

## Story Status

Stories should include a status field at the top using **standardized values**:

```markdown
## Status: Planned
```

**Valid status values:**
- **Planned**: Story is defined but not started
- **In Progress**: Actively being worked on
- **Complete**: Implementation finished and merged
- **Cancelled**: No longer planned (include reason in story)
- **Draft**: Early planning, not yet finalized
- **Ready**: Ready to start (dependencies met, design complete)
- **Hold**: Temporarily paused (include reason)
- **Postponed**: Deferred to future (include reason and target)

**Format:** Always use `## Status: {value}` (with colon) for consistency.

## How Stories Relate to GitHub Issues

**Important**: Stories are **NOT** GitHub Issues.

- **GitHub Issues** = Bugs, community feature requests, questions
- **Stories** = Internal planning documents for maintainers

When a community feature request becomes a planned story:
1. Create the story file here
2. Link to it from the GitHub Issue
3. Update the roadmap if it's user-facing

## Linking Stories to Work

When implementing a story:

1. **In PR description**: Reference the story
   ```markdown
   Implements Story 10.1: Configuration Presets
   See: docs/stories/10.1.configuration-presets.md
   ```

2. **When complete**: Update story status to "Complete"
   ```markdown
   ## Status: Complete
   ```

3. **If story addresses a GitHub Issue**: Link in PR and close issue
   ```markdown
   Closes #123
   Implements Story 10.1: docs/stories/10.1.configuration-presets.md
   ```

## Story Templates

We use standardized templates to ensure consistency:

### Individual Story Template

Use [`TEMPLATE_STORY.md`](./TEMPLATE_STORY.md) when creating a new story:

1. Copy the template: `cp TEMPLATE_STORY.md X.Y.story-name.md`
2. Fill in all sections
3. Remove any sections that don't apply (but keep the structure)

**Key sections:**
- **Status**: Use standardized values (Planned, In Progress, Complete, Cancelled, Draft, Ready, Hold, Postponed)
- **Priority**: Low, Medium, High, Critical
- **Estimated Effort**: Small (1 day), Medium (2-3 days), Large (1 week+), Epic
- **Dependencies**: Link to related stories
- **Acceptance Criteria**: Must be clear, testable, and independently verifiable
- **Tasks**: Break down into actionable, checkable items
- **Definition of Done**: Comprehensive checklist for story completion (code, QA, docs, review, compatibility)

### Series/Epic Overview Template

Use [`TEMPLATE_SERIES_OVERVIEW.md`](./TEMPLATE_SERIES_OVERVIEW.md) when creating a new series:

1. Copy the template: `cp TEMPLATE_SERIES_OVERVIEW.md X.0-series-overview.md`
2. Fill in series-level information
3. Create a table/list of all stories in the series
4. Document dependencies and implementation order

## Series/Epic Organization

Related stories are grouped into series (e.g., 10.x for Developer Experience):

- `X.0-series-overview.md` or `X.0-series-overview.md` - Overview of the entire series/epic
- `X.1.story-name.md` - Individual stories in the series

### Current Structure: Flat Organization

Stories are currently organized in a **flat structure**:
```
docs/stories/
  ├── 5.0-series-overview.md
  ├── 5.1.story-name.md
  ├── 5.2.another-story.md
  ├── 10.0-series-overview.md
  └── 10.1.configuration-presets.md
```

**Benefits:**
- ✅ Easy discovery (all stories in one place)
- ✅ Simple naming/numbering scheme
- ✅ Easy linking between stories
- ✅ Less directory navigation
- ✅ Works well with git history

### Alternative: Epics Folder Structure

If you prefer organizing by epic folders, you could use:
```
docs/stories/
  ├── epics/
  │   ├── plugin-system/
  │   │   ├── overview.md
  │   │   ├── 5.1.story.md
  │   │   └── 5.2.story.md
  │   └── developer-experience/
  │       ├── overview.md
  │       └── 10.1.story.md
```

**Considerations:**
- ⚠️ More directory navigation
- ⚠️ Need to decide folder naming (by number? by name?)
- ⚠️ Harder to see all stories at once
- ✅ Better organization for large numbers of stories
- ✅ Clearer epic boundaries

**Recommendation:** Keep the flat structure unless you have 50+ stories or find navigation difficult. The numbering scheme (5.x, 6.x, 10.x) already provides good organization.

## Finding Stories

- **By series**: Look for `{series}.0-series-overview.md` files
- **By status**: Search for `Status: {status}` in files
- **By topic**: Use your editor's search functionality

## Contributing Stories

If you're a maintainer planning new work:

1. Check if a story already exists (search this directory)
2. If not, create a new story file following the naming convention
3. Update the relevant series overview if applicable
4. Update `docs/roadmap.md` if it's a user-facing feature

## Templates

- **[TEMPLATE_STORY.md](./TEMPLATE_STORY.md)** - Template for individual stories
- **[TEMPLATE_SERIES_OVERVIEW.md](./TEMPLATE_SERIES_OVERVIEW.md)** - Template for series/epic overviews

## Standardization

We're standardizing story formats for consistency. See:

- **[STANDARDIZATION_GUIDE.md](./STANDARDIZATION_GUIDE.md)** - Format requirements and migration guide
- **[TEMPLATE_STORY.md](./TEMPLATE_STORY.md)** - Standard template for new stories
- **[TEMPLATE_SERIES_OVERVIEW.md](./TEMPLATE_SERIES_OVERVIEW.md)** - Standard template for series overviews

**Key standardization points:**
- Status format: `## Status: {value}` (standardized values)
- Metadata fields: Priority, Estimated Effort, Dependencies
- Consistent section structure
- Standardized status values (Planned, In Progress, Complete, Cancelled, Draft, Ready, Hold, Postponed)
- **Definition of Done**: Required comprehensive checklist for all stories

**Migration Status:**
- ✅ 19 active/planned stories migrated (2025-01-10)
- ✅ All include Definition of Done section
- See [MIGRATION_COMPLETE_SUMMARY.md](./MIGRATION_COMPLETE_SUMMARY.md) for details

## See Also

- [Story Management Recommendation](./STORY_MANAGEMENT_RECOMMENDATION.md) - Detailed strategy document
- [Migration Action Plan](./MIGRATION_ACTION_PLAN.md) - Step-by-step migration checklist
- [Migration Complete Summary](./MIGRATION_COMPLETE_SUMMARY.md) - Summary of completed migrations
- [Standardization Guide](./STANDARDIZATION_GUIDE.md) - Format requirements and migration guide
- [Roadmap](../roadmap.md) - Public-facing feature overview
- [Contributing Guide](../../CONTRIBUTING.md) - How to contribute to the project
