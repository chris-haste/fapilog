# Test Coverage & Quality Audit Report

**Date:** 2025-01-27  
**Auditor:** Staff/Principal Engineer (Python Quality Gates)  
**Scope:** READ-ONLY assessment of 90% coverage enforcement and test meaningfulness

---

## A) Executive Summary

### Current State

- **Coverage threshold:** 90% enforced in pre-commit, CI (tox), and coverage config
- **Actual coverage:** ~90.5% line coverage (from coverage.xml: 0.9048 line-rate)
- **Branch coverage:** **0%** (not enabled - critical gap)
- **Test files:** 698 Python files in `tests/` directory
- **Source files:** 104 Python files in `src/`
- **Quality gates:** Pre-commit hooks active (coverage, weak assertion linting, ruff, mypy, vulture)
- **CI pipeline:** GitHub Actions with separate lint, typecheck, test, and tox jobs
- **Weak assertions:** 174 violations baselined (not actively fixed)

### Biggest Risk Areas (Top 3)

1. **Branch Coverage Disabled (P0)**

   - Current: 0% branch coverage (`branch-rate="0"` in coverage.xml)
   - Risk: Can achieve 90% line coverage while missing critical conditional branches
   - Impact: High - allows coverage theater where tests hit lines but not all code paths

2. **Weak Assertions Baselined but Not Fixed (P1)**

   - 174 weak assertions in baseline (`.weak-assertion-baseline.txt`)
   - Patterns: `assert x >= 0`, `assert x >= 1`, `assert x is not None` without behavioral checks
   - Risk: Tests pass but don't verify actual behavior
   - Impact: Medium-High - tests may pass while bugs exist

3. **No Diff Coverage Enforcement (P1)**
   - No diff-cover or similar tool in CI/pre-commit
   - Risk: New code can be merged without tests if overall coverage stays above 90%
   - Impact: Medium - allows coverage to degrade incrementally

### Confidence Level: **MEDIUM**

**Why Medium:**

- ✅ Strong foundation: Pre-commit hooks, CI enforcement, weak assertion detection
- ✅ Good tooling: Custom `lint_test_assertions.py` script shows awareness
- ⚠️ Critical gap: Branch coverage disabled (0%)
- ⚠️ Baselined violations: 174 weak assertions tracked but not fixed
- ⚠️ No mutation testing or property-based testing
- ⚠️ Many `pass` statements in tests (141 matches) - may indicate incomplete tests

---

## B) Current Gates Inventory (Evidence-based)

### Pre-commit

**File:** `.pre-commit-config.yaml`

**Hooks:**

- `ruff` (linting) - with `--fix`
- `ruff-format` (formatting)
- `mypy` (type checking) - on `src/` only
- `vulture` (dead code detection)
- `coverage-check` - calls `scripts/check_coverage.py` (90% threshold)
- `lint-test-assertions` - calls `scripts/lint_test_assertions.py` with baseline
- `check-settings-descriptions`
- `pydantic-v1-check`
- `release-guardrails`
- `forbid-rst-in-docs`

**Key Settings:**

- Coverage check runs on `pre-commit` stage (always_run: true)
- Weak assertion linting uses baseline (`.weak-assertion-baseline.txt`) to suppress known violations

### CI Pipeline

**File:** `.github/workflows/ci.yml`

**Jobs:**

1. **lint** - Runs `hatch run lint:lint` (ruff check)
2. **typecheck** - Runs `hatch run typecheck:typecheck` (mypy)
3. **test** - Runs `hatch run test:test-cov` (pytest with coverage)
   - Uploads to Codecov (fail_ci_if_error: false - non-blocking)
4. **tox** - Runs `tox -q` (compatibility testing)

**Key Settings:**

- Test job runs on Python 3.11 only
- Coverage uploaded to Codecov but not enforced there
- Tox runs full test suite with `--cov-fail-under=90`

### Test Runner

**File:** `pyproject.toml` (sections: `[tool.pytest.ini_options]`, `[tool.hatch.envs.test]`)

**Configuration:**

- `testpaths = ["tests"]`
- `python_files = ["test_*.py", "*_test.py"]`
- `addopts = ["--strict-markers", "--strict-config", "--asyncio-mode=auto"]`
- Test command: `pytest --cov=src/fapilog --cov-report=html --cov-report=term tests`
- Markers: `slow`, `integration`, `benchmark`, `enterprise`, `security`

**Key Settings:**

- Async mode: `auto` (pytest-asyncio)
- Coverage source: `src/fapilog` only
- Reports: HTML and terminal

### Coverage Config

**File:** `pyproject.toml` (sections: `[tool.coverage.run]`, `[tool.coverage.report]`)

**Settings:**

```toml
[tool.coverage.run]
source = ["src"]
omit = [
    "*/tests/*",
    "*/test_*",
    "*/__pycache__/*",
]

[tool.coverage.report]
fail_under = 90
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if self.debug:",
    "if settings.DEBUG",
    "raise AssertionError",
    "raise NotImplementedError",
    "if 0:",
    "if __name__ == .__main__.:",
    "class .*\\bProtocol\\):",
    "@(abc\\.)?abstractmethod",
]
```

**Key Settings:**

- Threshold: 90% (enforced)
- Source: `src/` only
- Exclusions: Standard patterns + pragma comments
- **CRITICAL:** No branch coverage configuration

### Scripts/Make Targets

**Files:**

- `scripts/check_coverage.py` - Custom coverage checker (90% threshold, extracts from pytest output)
- `scripts/lint_test_assertions.py` - Weak assertion detector (WA001, WA002, WA003)
- `tox.ini` - Tox configuration with `--cov-fail-under=90`

**Key Settings:**

- `check_coverage.py` manually parses coverage percentage (avoids floating-point precision issues)
- `lint_test_assertions.py` supports baseline file to suppress known violations
- Tox runs: `ruff check .`, `mypy`, `lint_test_assertions.py`, `pytest --cov-fail-under=90`

---

## C) Coverage Implementation Details

### Coverage Toolchain

- **Tool:** `pytest-cov` (wrapper around `coverage.py`)
- **Version:** `pytest-cov>=6.2.0` (from pyproject.toml)
- **Coverage.py version:** 7.10.2 (from coverage.xml)

### Threshold and Where Enforced

1. **Pre-commit:** `scripts/check_coverage.py` (default: 90.0%, configurable via `--min-coverage`)
2. **CI (test job):** `hatch run test:test-cov` → pytest with coverage (no explicit fail-under in hatch script)
3. **CI (tox job):** `pytest --cov-fail-under=90` (explicit in tox.ini)
4. **Coverage config:** `[tool.coverage.report] fail_under = 90` (in pyproject.toml)

**Evidence:**

- `tox.ini:33`: `pytest tests/ --cov=src/fapilog --cov-report=term-missing --cov-fail-under=90`
- `pyproject.toml:339`: `fail_under = 90`
- `scripts/check_coverage.py:117`: `default=90.0`

### Line vs Branch

- **Line coverage:** ✅ Enabled (~90.5% from coverage.xml)
- **Branch coverage:** ❌ **NOT ENABLED** (`branch-rate="0"` in coverage.xml)
- **Complexity:** Not measured (`complexity="0"`)

**Evidence from coverage.xml:**

```xml
<coverage ... lines-valid="7941" lines-covered="7185" line-rate="0.9048"
          branches-covered="0" branches-valid="0" branch-rate="0" complexity="0">
```

**Gap:** No `--cov-branch` flag in pytest commands or coverage config.

### Exclusions/Omits

**Omit patterns:**

- `*/tests/*`
- `*/test_*`
- `*/__pycache__/*`

**Exclude lines (regex patterns):**

- `pragma: no cover`
- `def __repr__`
- `if self.debug:`
- `if settings.DEBUG`
- `raise AssertionError`
- `raise NotImplementedError`
- `if 0:`
- `if __name__ == .__main__.:`
- `class .*\\bProtocol\\):`
- `@(abc\\.)?abstractmethod`

**Pragma usage:** 92 instances of `# pragma: no cover` found across codebase (mostly defensive error paths, optional lifecycle hooks, type-checking-only code).

### Reporting Outputs

- **Terminal:** `--cov-report=term-missing` (shows missing lines)
- **HTML:** `--cov-report=html` (generates `htmlcov/`)
- **XML:** `--cov-report=xml` (generates `coverage.xml` for CI/Codecov)

**Evidence:**

- `pyproject.toml:162`: `test-cov = "pytest --cov=src/fapilog --cov-report=html --cov-report=term {args:tests}"`
- `scripts/check_coverage.py:47`: `--cov-report=xml`
- `coverage.xml` exists and is uploaded to Codecov

---

## D) Test Suite Quality Assessment

### Positive Signals (with examples)

1. **Custom Weak Assertion Linting**

   - **File:** `scripts/lint_test_assertions.py`
   - **Purpose:** Detects `assert x >= 0`, `assert x >= 1`, `assert x is not None` patterns
   - **Evidence:** 174 violations tracked in baseline, actively checked in pre-commit
   - **Example:** `tests/unit/test_error_handling.py:62-63` - multiple `is not None` checks

2. **Parameterized Tests**

   - **Evidence:** Found `@pytest.mark.parametrize` usage (e.g., `test_builtin_plugins_have_names.py`)
   - **Example:** `tests/unit/test_builtin_plugins_have_names.py:53` - parametrized plugin validation

3. **Integration Tests Present**

   - **Location:** `tests/integration/` (13 files)
   - **Examples:** CloudWatch, Loki, Postgres sinks, FastAPI middleware, audit trails
   - **Evidence:** Separate integration test suite with real dependencies

4. **Test Organization**

   - **Structure:** `tests/unit/` (140 files) + `tests/integration/` (13 files) + `tests/benchmark/`
   - **Naming:** Consistent `test_*.py` pattern
   - **Markers:** `@pytest.mark.integration`, `@pytest.mark.slow`, `@pytest.mark.security`

5. **Async Testing Support**
   - **Evidence:** `pytest-asyncio` with `--asyncio-mode=auto`
   - **Example:** `tests/unit/test_logger_pipeline.py` - comprehensive async logger tests

### Coverage-Theater Signals (with examples)

1. **Weak Assertions Baselined (174 violations)**

   - **File:** `.weak-assertion-baseline.txt`
   - **Patterns:**
     - WA001: `assert x >= 0` (always true for non-negative)
     - WA002: `assert x >= 1` (may be too weak)
     - WA003: `assert x is not None` (without behavioral check)
   - **Examples:**
     - `tests/unit/test_async_logger_facade.py:77-78`: `WA002`, `WA001`
     - `tests/unit/test_error_handling.py:62-63`: Multiple `WA003` (is not None)
     - `tests/unit/test_core_logger.py:97-98`: `WA002`, `WA001`
   - **Risk:** Tests pass but don't verify actual behavior

2. **Many `pass` Statements (141 matches)**

   - **Evidence:** `grep "pass\s*$" tests` found 141 matches
   - **Examples:**
     - `tests/unit/test_testing_validators.py:23,26,29,45,48,51` - multiple `pass` in mock classes
     - `tests/unit/test_plugin_name_utils.py:16,23,32,41` - `pass` in test plugin classes
   - **Context:** Many are in mock/test helper classes (acceptable), but some may indicate incomplete tests
   - **Risk:** Low-Medium (most appear to be mock implementations)

3. **No Branch Coverage**

   - **Impact:** Can achieve 90% line coverage while missing conditional branches
   - **Example:** `if error:` vs `if error is not None:` - both hit same line, but different branches
   - **Risk:** High - allows coverage theater

4. **Long Test Files with Many Pass Statements**
   - **Example:** `tests/unit/test_testing_validators.py` (530 lines) - many `pass` in mock classes
   - **Context:** Appears to be comprehensive validator tests with many mock implementations
   - **Risk:** Low (appears intentional for test utilities)

### Mocking Boundary Discipline (assessment)

**Evidence:**

- Found 25 instances of `patch()`, `Mock()`, `MagicMock()`, `monkeypatch` in tests
- **Examples:**
  - `tests/unit/test_logger_pipeline.py:77` - `patch("fapilog.core.settings.Settings")`
  - `tests/unit/test_logger_pipeline.py:1019` - `monkeypatch.setenv(...)`
- **Assessment:** ✅ **GOOD** - Mocking appears at I/O boundaries (settings, environment, diagnostics)
- **Risk:** Low - not mocking internals of units under test

### Flakiness Risks (time/random/etc)

**Evidence:**

- Found `time.sleep()` usage in tests (e.g., `tests/unit/test_logger_pipeline.py:732`)
- Found `asyncio.sleep()` in tests
- **Assessment:** ⚠️ **MODERATE RISK** - Time-dependent tests without freezing
- **Recommendation:** Review for flakiness, consider `freezegun` or `pytest-timeout`

**Examples:**

- `tests/unit/test_logger_pipeline.py:732`: `await asyncio.sleep(0.1)` in slow_sink
- `tests/unit/test_sink_circuit_breaker.py` - time-based circuit breaker tests

---

## E) Gap Analysis

### How the Current Setup Could be Gamed

1. **Branch Coverage Disabled**

   - **How:** Write tests that hit lines but not all branches
   - **Example:** `if x > 0: do_a()` - test with `x=1` hits line, but `x=0` branch untested
   - **Current protection:** None (branch coverage = 0%)

2. **Weak Assertions Baselined**

   - **How:** Use `assert x >= 0` or `assert x is not None` without behavioral checks
   - **Example:** `tests/unit/test_error_handling.py:62-63` - checks `is not None` but may not verify actual values
   - **Current protection:** Detected but baselined (not enforced)

3. **No Diff Coverage**

   - **How:** Add new code without tests if overall coverage stays above 90%
   - **Example:** Add 100 lines with 0% coverage, but if total coverage is 91%, it passes
   - **Current protection:** None (no diff-cover tool)

4. **Pragma: no cover Overuse**

   - **How:** Mark uncovered code as `# pragma: no cover` without justification
   - **Example:** 92 instances found (mostly legitimate, but no review process)
   - **Current protection:** None (no review gate for new pragmas)

5. **Integration Tests May Cover Unit Gaps**
   - **How:** Rely on integration tests to hit code paths, avoiding unit tests
   - **Example:** Integration test hits code, but unit test would catch bugs earlier
   - **Current protection:** None (coverage doesn't distinguish test types)

### Where Confidence is Genuinely High

1. **Core Logger Pipeline**

   - **Evidence:** `tests/unit/test_logger_pipeline.py` (1112+ lines) - comprehensive async tests
   - **Coverage:** Likely high (core functionality)

2. **Error Handling**

   - **Evidence:** `tests/unit/test_error_handling.py` (1756+ lines) - extensive error context tests
   - **Coverage:** Likely high (critical path)

3. **Integration Tests**

   - **Evidence:** 13 integration test files covering real dependencies (CloudWatch, Loki, Postgres)
   - **Coverage:** High confidence in end-to-end scenarios

4. **Plugin Validation**
   - **Evidence:** `tests/unit/test_testing_validators.py` (530 lines) - comprehensive protocol validation
   - **Coverage:** High confidence in plugin contract enforcement

### Where Confidence is Misleading

1. **Branch Coverage = 0%**

   - **Risk:** Conditional logic may be untested
   - **Example:** `if error:` vs `if error is not None:` - both hit same line, different branches
   - **Impact:** High - critical branches may be untested

2. **Weak Assertions (174 baselined)**

   - **Risk:** Tests pass but don't verify behavior
   - **Example:** `assert x is not None` without checking `x.field == expected`
   - **Impact:** Medium-High - tests may pass while bugs exist

3. **No Mutation Testing**

   - **Risk:** Tests may pass but not catch bugs (weak tests)
   - **Example:** Test checks `assert result is not None` but doesn't verify `result.value == expected`
   - **Impact:** Medium - tests may be too weak

4. **No Property-Based Testing**
   - **Risk:** Edge cases may be missed
   - **Example:** Manual test cases may miss boundary conditions
   - **Impact:** Low-Medium - property-based tests would catch more edge cases

---

## F) Recommendations (Prioritized)

### P0 (Do Next) - Critical Gaps

#### 1. Enable Branch Coverage

**Why:** Current 0% branch coverage allows coverage theater - tests can hit lines without testing all code paths.

**Where:**

- `pyproject.toml` - Add `[tool.coverage.run] branch = true`
- `tox.ini:33` - Add `--cov-branch` to pytest command
- `scripts/check_coverage.py:45` - Add `--cov-branch` to pytest command
- `.github/workflows/ci.yml` - Update hatch test-cov script to include branch coverage

**What:**

```toml
[tool.coverage.run]
source = ["src"]
branch = true  # ADD THIS
omit = [...]
```

```ini
# tox.ini
commands =
    pytest tests/ --cov=src/fapilog --cov-branch --cov-report=term-missing --cov-fail-under=90
```

**Expected Impact:**

- CI impact: **Medium** (may reveal uncovered branches, causing initial failures)
- Runtime: Low (minimal overhead)
- False positives: Low (legitimate gaps)
- Dev friction: Medium (may require fixing uncovered branches)

**Tradeoffs:**

- May drop coverage below 90% initially (need to fix branches)
- Better confidence in test quality
- Catches conditional logic bugs

#### 2. Require Branch Coverage Threshold

**Why:** Enable branch coverage but also enforce a minimum threshold (e.g., 85%).

**Where:**

- `pyproject.toml` - Add `[tool.coverage.report] precision = 1` and document branch threshold
- `scripts/check_coverage.py` - Add branch coverage percentage check

**What:**

```python
# scripts/check_coverage.py - Add branch coverage extraction and check
branch_coverage = extract_branch_coverage_from_output(result.stdout)
branch_threshold = 85.0  # Configurable
if branch_coverage < branch_threshold:
    print(f"FAILED: Branch coverage {branch_coverage:.1f}% < {branch_threshold:.1f}%")
    return 1
```

**Expected Impact:**

- CI impact: **High** (new gate that may fail initially)
- Runtime: Low
- False positives: Medium (may need to adjust threshold)
- Dev friction: High (requires fixing branch coverage)

**Tradeoffs:**

- Higher quality bar
- More work to maintain
- Better confidence

### P1 (Do Soon) - High Value

#### 3. Add Diff Coverage Gate

**Why:** Prevents new code from being merged without tests, even if overall coverage stays above 90%.

**Where:**

- `.pre-commit-config.yaml` - Add `diff-cover` hook
- `.github/workflows/ci.yml` - Add diff-cover step in test job

**What:**

```yaml
# .pre-commit-config.yaml
- repo: https://github.com/Bachmann1234/diff-cover
  rev: v7.7.0
  hooks:
    - id: diff-cover
      args: ["--fail-under=90", "--compare-branch=origin/main"]
```

```yaml
# .github/workflows/ci.yml - Add step after coverage
- name: Diff coverage
  run: |
    pip install diff-cover
    diff-cover coverage.xml --compare-branch=origin/main --fail-under=90
```

**Expected Impact:**

- CI impact: **Medium** (new gate, may fail on PRs with untested changes)
- Runtime: Low (runs after coverage)
- False positives: Low
- Dev friction: Medium (requires tests for new code)

**Tradeoffs:**

- Prevents coverage degradation
- Enforces tests for new code
- May require baseline for legacy code

#### 4. Tighten Weak Assertion Enforcement

**Why:** 174 baselined violations indicate systemic issue - should be fixed, not suppressed.

**Where:**

- `scripts/lint_test_assertions.py` - Make baseline violations warnings (not errors) but track progress
- Add PR review gate: "No new weak assertions without justification"

**What:**

```python
# scripts/lint_test_assertions.py - Add --strict mode
if args.strict and new_violations:
    print("ERROR: New weak assertions not allowed in strict mode")
    return 1
```

**Expected Impact:**

- CI impact: **Low** (can be gradual - warn first, then enforce)
- Runtime: Low (same script)
- False positives: Low (heuristics are reasonable)
- Dev friction: Medium (requires fixing weak assertions)

**Tradeoffs:**

- Better test quality
- Requires fixing 174 baselined violations
- Can be phased (warn → enforce)

#### 5. Add Pragma Review Gate

**Why:** 92 `pragma: no cover` instances - need justification for new ones.

**Where:**

- `.pre-commit-config.yaml` - Add hook to detect new `pragma: no cover` without justification comment
- PR template - Add checklist: "New `pragma: no cover` requires justification"

**What:**

```python
# scripts/check_pragma_no_cover.py (new script)
# Detect new pragma: no cover without justification comment
# Require format: # pragma: no cover - <reason>
```

**Expected Impact:**

- CI impact: **Low** (review gate, not blocking)
- Runtime: Low
- False positives: Low
- Dev friction: Low (just requires comment)

**Tradeoffs:**

- Prevents abuse of pragma
- Documents why code is excluded
- Low overhead

### P2 (Later / Optional) - Advanced Quality

#### 6. Mutation Testing (Selective)

**Why:** Detects weak tests that pass but don't catch bugs.

**Where:**

- `.github/workflows/ci.yml` - Add nightly mutation testing job (not blocking)
- Or: Run on changed modules only (PR-based)

**What:**

```yaml
# .github/workflows/ci.yml - Add job
mutation-test:
  name: Mutation Testing (Nightly)
  runs-on: ubuntu-latest
  if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'
  steps:
    - uses: actions/checkout@v4
    - name: Install mutmut
      run: pip install mutmut
    - name: Run mutation testing on core modules
      run: mutmut run --paths-to-mutate=src/fapilog/core/
```

**Expected Impact:**

- CI impact: **Low** (nightly, not blocking)
- Runtime: **High** (mutation testing is slow)
- False positives: Medium (some mutations may be equivalent)
- Dev friction: Low (not blocking)

**Tradeoffs:**

- Catches weak tests
- Very slow (hours for full suite)
- Best for critical modules only

#### 7. Property-Based Testing (Hypothesis)

**Why:** Catches edge cases that manual tests miss.

**Where:**

- Add `hypothesis>=6.0.0` to `[project.optional-dependencies.dev]`
- Use in critical modules (serialization, validation, error handling)

**What:**

```python
# Example: tests/unit/test_serialization.py
from hypothesis import given, strategies as st

@given(st.dictionaries(st.text(), st.one_of(st.text(), st.integers(), st.booleans())))
def test_serialize_roundtrip(data):
    serialized = serialize(data)
    deserialized = deserialize(serialized)
    assert deserialized == data
```

**Expected Impact:**

- CI impact: **Low** (adds tests, doesn't change gates)
- Runtime: Medium (property tests can be slower)
- False positives: Low
- Dev friction: Low (optional, incremental)

**Tradeoffs:**

- Catches edge cases
- Requires learning Hypothesis
- Best for data transformation logic

#### 8. Test Smell Static Analysis

**Why:** Detects common test anti-patterns (no assertions, too many mocks, etc.).

**Where:**

- `.pre-commit-config.yaml` - Add custom hook or use existing tool

**What:**

```python
# scripts/lint_test_smells.py (new script)
# Detect:
# - Tests with no assertions
# - Tests with only mock.assert_called() (no outcome check)
# - Tests with >5 mocks (may be over-mocked)
# - Tests with time.sleep() without freezing
```

**Expected Impact:**

- CI impact: **Low** (heuristic-based, may have false positives)
- Runtime: Low
- False positives: Medium (heuristics may flag legitimate patterns)
- Dev friction: Low (warnings, not errors)

**Tradeoffs:**

- Catches common issues
- May have false positives
- Best as advisory (warnings, not errors)

---

## G) Proposed Change List (NO CODE, just plan)

### File: `pyproject.toml`

**Change:** Add `branch = true` to `[tool.coverage.run]` section  
**Validation:** Run `pytest --cov=src/fapilog --cov-branch --cov-report=term` and verify branch coverage appears

### File: `tox.ini`

**Change:** Add `--cov-branch` to pytest command on line 33  
**Validation:** Run `tox` and verify branch coverage is reported

### File: `scripts/check_coverage.py`

**Change:**

1. Add `--cov-branch` to pytest command (line 45)
2. Extract branch coverage percentage from output
3. Add branch coverage threshold check (e.g., 85%)
   **Validation:** Run `python scripts/check_coverage.py` and verify branch coverage is checked

### File: `.pre-commit-config.yaml`

**Change:** Add `diff-cover` hook after coverage-check  
**Validation:** Run `pre-commit run diff-cover --all-files` and verify it works

### File: `.github/workflows/ci.yml`

**Change:**

1. Update test job to include `--cov-branch` in hatch test-cov script
2. Add diff-cover step after coverage upload
   **Validation:** Create test PR and verify CI runs diff-cover

### File: `scripts/lint_test_assertions.py`

**Change:** Add `--strict` mode that fails on new weak assertions (not baselined)  
**Validation:** Run with `--strict` and verify it fails on new violations

### File: `scripts/check_pragma_no_cover.py` (NEW)

**Change:** Create script to detect new `pragma: no cover` without justification comments  
**Validation:** Run on PR and verify it flags new pragmas without comments

### File: `.github/workflows/ci.yml` (optional)

**Change:** Add nightly mutation testing job (not blocking)  
**Validation:** Trigger workflow and verify mutation testing runs

---

## H) Appendix

### Commands Run + Key Outputs

```bash
# Test file count
find . -name "*.py" -path "*/tests/*" | wc -l
# Output: 698

# Source file count
find . -name "*.py" -path "*/src/*" | wc -l
# Output: 104

# Coverage XML branch rate
cat coverage.xml | grep -E "line-rate|branch-rate" | head -5
# Output: branch-rate="0" (NOT ENABLED)

# Weak assertions
grep "assert\s+True|assert\s+1\s*==\s*1|pass\s*$" tests
# Output: 141 matches (mostly `pass` in mock classes)

# Pragma no cover count
grep -r "pragma:\s*no cover" . --include="*.py" | wc -l
# Output: 92 instances

# Mocking usage
grep "mocker\.patch|monkeypatch|patch\(|Mock\(|MagicMock\(" tests | wc -l
# Output: 25 instances (reasonable - at I/O boundaries)
```

### Items that were CANNOT VERIFY

1. **Actual test execution time**

   - **What I'd need:** Run `pytest --durations=10` to see slowest tests
   - **Why:** To assess if slow tests encourage shortcuts

2. **Coverage per module/package**

   - **What I'd need:** Run `coverage report --show-missing` to see per-module breakdown
   - **Why:** To identify modules with low coverage that may need attention

3. **Mutation testing results**

   - **What I'd need:** Run `mutmut run` on a sample module
   - **Why:** To assess actual test strength (how many mutations survive)

4. **Property-based testing feasibility**

   - **What I'd need:** Identify specific modules that would benefit (serialization, validation)
   - **Why:** To prioritize where Hypothesis would add most value

5. **Diff coverage baseline**

   - **What I'd need:** Run `diff-cover` on current codebase to see baseline
   - **Why:** To set realistic threshold for new code

6. **Test flakiness rate**
   - **What I'd need:** Run test suite multiple times to measure flakiness
   - **Why:** To identify time-dependent or race condition issues

---

## Summary

**Current State:** Strong foundation with 90% coverage enforcement, but critical gap in branch coverage (0%) and 174 weak assertions baselined.

**Biggest Risks:**

1. Branch coverage disabled (P0)
2. Weak assertions not fixed (P1)
3. No diff coverage (P1)

**Recommended Actions:**

1. **Enable branch coverage** (P0) - Highest impact, medium effort
2. **Add diff coverage gate** (P1) - Prevents coverage degradation
3. **Tighten weak assertion enforcement** (P1) - Improves test quality
4. **Add pragma review gate** (P1) - Prevents abuse
5. **Consider mutation testing** (P2) - Advanced quality signal

**Confidence Level:** MEDIUM - Good foundation, but branch coverage gap is critical.
