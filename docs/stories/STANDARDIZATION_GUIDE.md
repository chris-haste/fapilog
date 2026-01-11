# Story Format Standardization Guide

This guide explains the standardized story format and how to migrate existing stories.

## Why Standardize?

**Current Issues:**
- Inconsistent status formats (`## Status:`, `**Status:**`, `## Status`)
- Varying status values (Complete, Completed, Ready, Draft, etc.)
- Different section structures across stories
- Missing metadata (Priority, Effort, Dependencies)
- Inconsistent epic/series references

**Benefits of Standardization:**
- ✅ Easier to find and filter stories
- ✅ Consistent structure for maintainers
- ✅ Better tooling support (scripts, automation)
- ✅ Clearer communication
- ✅ Easier onboarding for new contributors

## Standard Format Requirements

### 1. Status Field

**Required format:**
```markdown
## Status: {value}
```

**Valid values:**
- `Planned` - Story is defined but not started
- `In Progress` - Actively being worked on
- `Complete` - Implementation finished and merged
- `Cancelled` - No longer planned (include reason)
- `Draft` - Early planning, not yet finalized
- `Ready` - Ready to start (dependencies met, design complete)
- `Hold` - Temporarily paused (include reason)
- `Postponed` - Deferred to future (include reason)

**Examples:**
- ✅ `## Status: Complete`
- ✅ `## Status: In Progress`
- ❌ `**Status:** Complete` (wrong format)
- ❌ `## Status` (missing value)
- ❌ `Status: Completed` (use "Complete", not "Completed")

### 2. Metadata Fields (Recommended)

Add these fields after Status for better organization:

```markdown
## Priority: {Low | Medium | High | Critical}
## Estimated Effort: {Small (1 day) | Medium (2-3 days) | Large (1 week+) | Epic}
## Dependencies
- **Depends on:** Story X.Y (if applicable)
- **Prerequisite for:** Story X.Z (if applicable)
## Epic / Series
Part of Epic {Name} / Series {X.x}
```

### 3. Required Sections

All stories should include:

1. **Title** - `# Story {X.Y}: {Title}`
2. **Status** - `## Status: {value}`
3. **Context / Background** - Why this work is needed
4. **Scope (In / Out)** - What's included/excluded
5. **Acceptance Criteria** - Clear, testable criteria
6. **Tasks** - Implementation checklist
7. **Tests** - Testing requirements
8. **Definition of Done** - Comprehensive completion checklist (REQUIRED)

### 4. Optional Sections

Include as needed:

- **User Story** - For user-facing features
- **Priority** - Low, Medium, High, Critical
- **Estimated Effort** - Small, Medium, Large, Epic
- **Dependencies** - Links to related stories
- **Epic / Series** - Which epic/series it belongs to
- **Technical Design / Implementation Notes** - For complex stories
- **Documentation Updates** - Checklist for docs
- **Risks / Rollback / Monitoring** - For high-risk stories
- **Related Documents** - Links to related docs
- **Change Log** - History of changes

## Migration Checklist

When updating an existing story to the standard format:

### Step 1: Fix Status Field

- [ ] Ensure status uses format: `## Status: {value}`
- [ ] Use standardized status value (see list above)
- [ ] Remove any alternative formats (`**Status:**`, etc.)

### Step 2: Add Missing Metadata

- [ ] Add Priority field (if not present)
- [ ] Add Estimated Effort (if not present)
- [ ] Add Dependencies section (if applicable)
- [ ] Add Epic/Series reference (if applicable)

### Step 3: Standardize Sections

- [ ] Ensure "Context / Background" section exists
- [ ] Ensure "Scope (In / Out)" section exists
- [ ] Ensure "Acceptance Criteria" section exists
- [ ] Ensure "Tasks" section exists
- [ ] Ensure "Tests" section exists
- [ ] **Add "Definition of Done" section** (REQUIRED - most important addition)

### Step 4: Format Consistency

- [ ] Use consistent heading levels (## for main sections)
- [ ] Use consistent checkbox format (`- [ ]`)
- [ ] Use consistent table format (if using tables)
- [ ] Ensure all links use relative paths

### Step 5: Review

- [ ] Story follows [TEMPLATE_STORY.md](./TEMPLATE_STORY.md) structure
- [ ] All sections are filled in appropriately
- [ ] No placeholder text remains
- [ ] Status accurately reflects current state

## Definition of Done Section

**NEW REQUIREMENT**: All stories must include a Definition of Done section.

The Definition of Done provides a comprehensive checklist to ensure stories are truly complete before marking them as done. It includes:

### Code Complete
- All acceptance criteria met and verified
- All tasks completed
- Code follows project style guide
- No linting errors or warnings
- Type checking passes (mypy strict)

### Quality Assurance
- Unit tests: >90% coverage of new code
- Integration tests: all scenarios passing
- Regression tests: no existing functionality broken
- Performance tests: no regression vs baseline
- Manual testing completed (if applicable)

### Documentation
- User-facing docs updated
- API reference updated (if applicable)
- Code examples added/updated
- CHANGELOG.md updated
- Inline code documentation complete

### Review & Release
- Code review approved
- Documentation reviewed for clarity
- CI/CD pipeline passing
- Ready for merge to main branch

### Backwards Compatibility
- No breaking changes OR breaking changes documented with migration guide
- Existing tests still pass
- Deprecation warnings added (if applicable)

**Placement**: The Definition of Done section should be placed after "Documentation Updates" and before "Risks / Rollback / Monitoring".

## Examples

### Before (Inconsistent)

```markdown
# Story 5.1: Fix Plugin Metadata

**Status:** Complete

## Problem

The plugin audit revealed inconsistencies...

## Acceptance Criteria

1. All PLUGIN_METADATA names are consistent
2. No suffixes in names
```

### After (Standardized)

```markdown
# Story 5.1: Fix Plugin Metadata Inconsistencies

## Status: Complete

## Priority: Critical

## Estimated Effort: Small (1 day)

## Dependencies: None

## Epic / Series

Part of Epic Plugin System Completion / Series 5.x

---

## Context / Background

The plugin audit revealed inconsistencies between the `name` class attribute on plugin classes and the `name` field in `PLUGIN_METADATA`. This creates confusion when users reference plugins by name in configuration.

---

## Acceptance Criteria

### AC1: Consistent Naming Convention

- [ ] All `PLUGIN_METADATA["name"]` values use underscore format
- [ ] Decision documented in `docs/plugins/authoring.md`

### AC2: No Suffixes in Names

- [ ] Remove `-enricher`, `-redactor`, `-sink` suffixes from PLUGIN_METADATA
- [ ] Plugin type is already specified in `plugin_type` field

---

## Definition of Done

Story is complete when ALL of the following are true:

### Code Complete
- [ ] All acceptance criteria met and verified
- [ ] All tasks completed
- [ ] Code follows project style guide
- [ ] No linting errors or warnings
- [ ] Type checking passes (mypy strict)

[... rest of DoD checklist ...]
```

## Series Overview Standardization

Series overview files should follow [`TEMPLATE_SERIES_OVERVIEW.md`](./TEMPLATE_SERIES_OVERVIEW.md):

### Required Sections

1. **Title** - `# Story Series {X.x}: {Epic/Series Name}`
2. **Overview** - Brief description
3. **Context / Background** - Why this series is needed
4. **Stories** - Table/list of all stories
5. **Dependency Graph** - Visual representation (optional but recommended)
6. **Success Metrics** - Series-level criteria

### Recommended Sections

- **Guiding Principles** - If applicable
- **Implementation Order** - Recommended sequence
- **Total Effort Estimate** - Summary table
- **Risks / Mitigation** - Series-level risks
- **Change Log** - History of changes

## Automation Opportunities

Once standardized, you can:

1. **Status Reports** - Script to generate status reports:
   ```bash
   grep -r "^## Status:" docs/stories/ | sort
   ```

2. **Dependency Analysis** - Parse dependencies to build graphs

3. **Completion Tracking** - Count stories by status

4. **Template Validation** - Check stories match template structure

## Gradual Migration Strategy

You don't need to migrate all stories at once:

1. **New stories** - Always use the template (includes Definition of Done)
2. **Active stories** - Migrate when updating (add Definition of Done)
3. **Complete stories** - Migrate when time permits (or skip if rarely referenced)
4. **Draft stories** - Migrate before marking as "Ready" (add Definition of Done)

**Migration Status (2025-01-10):**
- ✅ 19 active/planned stories already migrated
- ✅ All include Definition of Done section
- See [MIGRATION_COMPLETE_SUMMARY.md](./MIGRATION_COMPLETE_SUMMARY.md)

## Migration Status

**As of 2025-01-10:**
- ✅ 19 active/planned stories migrated to new format
- ✅ All migrated stories include Definition of Done
- ✅ Template updated with Definition of Done section
- ⏭️ Remaining stories will be migrated gradually as they're worked on

See [MIGRATION_COMPLETE_SUMMARY.md](./MIGRATION_COMPLETE_SUMMARY.md) for details.

## Questions?

- See [TEMPLATE_STORY.md](./TEMPLATE_STORY.md) for full template
- See [TEMPLATE_SERIES_OVERVIEW.md](./TEMPLATE_SERIES_OVERVIEW.md) for series template
- See [README.md](./README.md) for general guidelines
- See [MIGRATION_COMPLETE_SUMMARY.md](./MIGRATION_COMPLETE_SUMMARY.md) for migration status
