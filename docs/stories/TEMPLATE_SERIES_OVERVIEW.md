# Story Series {X.x}: {Epic/Series Name}

## Overview

Brief description of the series/epic. What is the high-level goal? What problems does this series solve?

---

## Context / Background

Why is this series needed? What is the current state? What gaps or opportunities does it address?

---

## Guiding Principles (Optional)

If applicable, list principles that guide decisions in this series:

1. **Principle 1:** Description
2. **Principle 2:** Description
3. **Principle 3:** Description

---

## Stories

### Quick Reference Table

| Story | Title | Priority | Effort | Status | Dependencies |
| ----- | ----- | -------- | ------ | ------ | ------------ |
| X.0   | [Series Overview](./X.0-series-overview.md) | - | - | - | - |
| X.1   | [Story Title](./X.1.story-name.md) | High | Medium | Planned | None |
| X.2   | [Story Title](./X.2.story-name.md) | Medium | Small | In Progress | X.1 |
| X.3   | [Story Title](./X.3.story-name.md) | Low | Large | Draft | X.2 |

### Story Details

#### Phase 1: {Phase Name}

**Goal:** Brief description of phase goal

| Story | Title | Description | Status |
| ----- | ----- | ----------- | ------ |
| X.1   | Story Name | Brief description | Planned |
| X.2   | Story Name | Brief description | Planned |

**Success Criteria:**
- [ ] Criterion 1
- [ ] Criterion 2

#### Phase 2: {Phase Name}

[Similar structure...]

---

## Dependency Graph

```
X.1 Foundation ──────┬──► X.2 Feature A ──► X.3 Feature B
                    │
                    └──► X.4 Feature C (parallel)

X.5 Independent ───────────────────────────► (can proceed in parallel)
```

---

## Implementation Order

### Recommended Sequence

1. **Week 1:** Stories X.1, X.2 (foundation)
2. **Week 2:** Stories X.3, X.4 (parallel tracks)
3. **Week 3:** Story X.5 (integration)

### Parallel Work Tracks

For teams with multiple developers:

**Track A (Core):** X.1 → X.2 → X.3  
**Track B (Features):** X.4, X.5 (parallel, independent)  
**Track C (Polish):** X.6 (can start after X.1)

---

## Total Effort Estimate

| Priority  | Story Count | Total Effort    |
| --------- | ----------- | --------------- |
| Critical  | 2           | ~4-6 days       |
| High      | 3           | ~8-10 days      |
| Medium    | 2           | ~4-6 days       |
| Low       | 1           | ~2-3 days       |
| **Total** | **8**       | **~18-25 days** |

---

## Scope (In / Out)

### In Scope

- What's included in this series
- Key deliverables
- Success criteria

### Out of Scope

- What's explicitly not included
- Related work deferred to other series
- Future considerations

---

## Success Metrics

### Series-Level Metrics

- [ ] Metric 1: Description and target
- [ ] Metric 2: Description and target
- [ ] User adoption/feedback indicators

### Phase Completion Criteria

**Phase 1 Complete:**
- [ ] All Phase 1 stories complete
- [ ] Integration tests passing
- [ ] Documentation updated

**Phase 2 Complete:**
- [ ] All Phase 2 stories complete
- [ ] Performance benchmarks met
- [ ] User feedback positive

---

## Risks / Mitigation

### Risks

- **Risk 1:** Description
  - **Impact:** High/Medium/Low
  - **Mitigation:** Strategy
- **Risk 2:** Description
  - **Impact:** High/Medium/Low
  - **Mitigation:** Strategy

---

## Related Documents

- [Epic Document](../prd/epic-X-...md)
- [Architecture Docs](../architecture/...md)

---

## Change Log

| Date       | Change                                    | Author |
| ---------- | ----------------------------------------- | ------ |
| YYYY-MM-DD | Initial series creation                   | {name} |
| YYYY-MM-DD | Added Story X.3, updated dependencies     | {name} |
| YYYY-MM-DD | Completed Phase 1, updated statuses       | {name} |
