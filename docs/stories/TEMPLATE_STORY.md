# Story {X.Y}: {Title}

## Status: Planned

**Valid status values:** `Planned`, `In Progress`, `Complete`, `Cancelled`, `Draft`, `Ready`, `Hold`, `Postponed`

## Priority: {Low | Medium | High | Critical}

## Estimated Effort: {Small (1 day) | Medium (2-3 days) | Large (1 week+) | Epic}

## Dependencies

- **Depends on:** Story X.Z (if applicable)
- **Prerequisite for:** Story X.W (if applicable)
- **Related to:** Story Y.Z (if applicable)

## Epic / Series

Part of Epic {Name} / Series {X.x}

---

## Context / Background

Why is this work needed? What problem does it solve? What is the current state?

Provide sufficient context for someone new to understand:
- The business/technical need
- Current limitations or pain points
- How this story addresses them

---

## User Story (Optional)

**As a** {role}  
**I want** {functionality}  
**So that** {benefit/value}

*Note: User story format is optional but recommended for user-facing features.*

---

## Scope (In / Out)

### In Scope

- What will be included in this story
- Specific features, components, or changes
- Clear boundaries

### Out of Scope

- What's explicitly not included (and why)
- Related work deferred to other stories
- Future considerations

---

## Acceptance Criteria

Each criterion should be:
- **Clear and testable**
- **Independently verifiable**
- **Specific enough to validate completion**

### AC1: {Criterion Name}

- [ ] Specific, testable requirement
- [ ] Another specific requirement
- [ ] Success metric or validation method

### AC2: {Another Criterion}

- [ ] Requirement 1
- [ ] Requirement 2

---

## Technical Design / Implementation Notes

### Architecture Decisions

- Key technical decisions and rationale
- Design patterns or approaches
- Integration points with existing code

### Implementation Approach

- High-level implementation strategy
- Key components/modules involved
- Data structures or APIs

### Code Locations

- Primary files/modules to modify:
  - `src/fapilog/core/logger.py`
  - `src/fapilog/plugins/sinks/...`
- New files to create:
  - `src/fapilog/core/new_feature.py`

### Dependencies & Constraints

- External dependencies (if any)
- Backward compatibility requirements
- Performance considerations
- Security considerations

---

## Tasks

Break down into actionable, checkable tasks:

### Phase 1: Foundation
- [ ] Task 1: Create new module structure
- [ ] Task 2: Add configuration options
- [ ] Task 3: Write unit tests for core logic

### Phase 2: Integration
- [ ] Task 4: Integrate with existing system
- [ ] Task 5: Update documentation
- [ ] Task 6: Add integration tests

### Phase 3: Polish
- [ ] Task 7: Error handling and edge cases
- [ ] Task 8: Performance optimization
- [ ] Task 9: Final documentation review

---

## Tests

### Unit Tests

- [ ] Test case 1: {description}
- [ ] Test case 2: {description}
- [ ] Edge cases and error conditions

### Integration Tests

- [ ] Integration scenario 1
- [ ] Integration scenario 2
- [ ] End-to-end workflow

### Manual Verification

- [ ] Manual test step 1
- [ ] Manual test step 2

### Performance / Benchmarks

- [ ] Benchmark baseline
- [ ] Benchmark with changes
- [ ] Performance regression tests (if applicable)

---

## Documentation Updates

- [ ] Update user guide: `docs/user-guide/...`
- [ ] Update API reference: `docs/api-reference/...`
- [ ] Add examples: `examples/...`
- [ ] Update CHANGELOG.md
- [ ] Update roadmap (if user-facing)

---

## Definition of Done

Story is complete when ALL of the following are true:

### Code Complete
- [ ] All acceptance criteria met and verified
- [ ] All tasks completed
- [ ] Code follows project style guide
- [ ] No linting errors or warnings
- [ ] Type checking passes (mypy strict)

### Quality Assurance
- [ ] Unit tests: >90% coverage of new code
- [ ] Integration tests: all scenarios passing
- [ ] Regression tests: no existing functionality broken
- [ ] Performance tests: no regression vs baseline
- [ ] Manual testing completed (if applicable)

### Documentation
- [ ] User-facing docs updated
- [ ] API reference updated (if applicable)
- [ ] Code examples added/updated
- [ ] CHANGELOG.md updated
- [ ] Inline code documentation complete

### Review & Release
- [ ] Code review approved
- [ ] Documentation reviewed for clarity
- [ ] CI/CD pipeline passing
- [ ] Ready for merge to main branch

### Backwards Compatibility
- [ ] No breaking changes OR breaking changes documented with migration guide
- [ ] Existing tests still pass
- [ ] Deprecation warnings added (if applicable)

---

## Risks / Rollback / Monitoring

### Risks

- **Risk 1:** Description of potential issue
  - **Mitigation:** How to prevent or handle it
- **Risk 2:** Another potential issue
  - **Mitigation:** Mitigation strategy

### Rollback Plan

- How to revert if needed
- What can be safely rolled back
- Data migration considerations (if any)

### Success Metrics / Monitoring

- How to measure success
- Metrics to track
- Monitoring/observability requirements
- User feedback mechanisms

---

## Related Documents

- [Series Overview](./X.0-series-overview.md)
- [Epic Document](../prd/epic-X-...md)
- [Architecture Docs](../architecture/...md)
- [Related Story](./X.Z.related-story.md)

---

## Change Log

| Date       | Change                                    | Author |
| ---------- | ----------------------------------------- | ------ |
| YYYY-MM-DD | Initial story creation                    | {name} |
| YYYY-MM-DD | Updated acceptance criteria based on feedback | {name} |
