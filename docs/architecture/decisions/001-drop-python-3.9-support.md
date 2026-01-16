# ADR-001: Drop Python 3.9 Support

**Status:** Accepted
**Date:** 2026-01-16
**Decision Makers:** Chris Haste

## Context

The nightly CI build for fapilog began failing on Python 3.9 due to type annotation syntax incompatibility. The codebase uses modern union syntax (`X | None`) which is only supported at runtime in Python 3.10+.

While `from __future__ import annotations` defers annotation evaluation for most Python code, Pydantic v2 evaluates type annotations at runtime for model validation. This causes failures when importing modules containing Pydantic models with union syntax on Python 3.9.

### Options Considered

1. **Replace `X | None` with `Optional[X]`** in all Pydantic models
   - Pros: No new dependencies, backwards compatible
   - Cons: Requires changing many files, mixes syntax styles, ongoing maintenance burden

2. **Add `eval_type_backport` dependency**
   - Pros: Minimal code changes
   - Cons: Adds runtime dependency for all users, including those on Python 3.10+ who don't need it

3. **Drop Python 3.9 support**
   - Pros: Clean modern syntax, no dependency bloat, reduced maintenance
   - Cons: Users still on 3.9 would need to upgrade

## Decision

**Drop Python 3.9 support.** Minimum supported version is now Python 3.10.

## Rationale

1. **Python 3.9 reached end-of-life in October 2025.** It no longer receives security patches, and users should upgrade to supported versions.

2. **Pydantic v2 pushes toward modern Python.** The library ecosystem is moving forward, and fapilog already requires Pydantic v2.11+.

3. **Reduced maintenance burden.** Supporting EOL Python versions requires ongoing workarounds and prevents using modern language features.

4. **Library best practice.** Supporting only maintained Python versions aligns with community standards and security best practices.

## Consequences

### Positive

- Codebase can freely use Python 3.10+ syntax features (union types, pattern matching, etc.)
- No additional dependencies required for type annotation compatibility
- Cleaner, more consistent codebase
- Aligns with Python community security recommendations

### Negative

- Users on Python 3.9 must upgrade before using newer fapilog versions
- Existing users on 3.9 are locked to older fapilog releases

### Neutral

- CI matrix reduced by one version (minor build time improvement)

## Implementation

1. Update `pyproject.toml`: `requires-python = ">=3.10"`
2. Remove Python 3.9 classifier from pyproject.toml
3. Remove Python 3.9 from CI workflow matrices
4. Update documentation to reflect new minimum version

## References

- [Python 3.9 EOL](https://devguide.python.org/versions/) - October 2025
- [PEP 604](https://peps.python.org/pep-0604/) - Union types with `X | Y` syntax (Python 3.10+)
- [Pydantic v2 Type Annotation Handling](https://docs.pydantic.dev/latest/concepts/types/)
