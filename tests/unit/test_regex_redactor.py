from __future__ import annotations

import pytest

from fapilog.plugins.redactors.regex_mask import (
    RegexMaskConfig,
    RegexMaskRedactor,
)

pytestmark = pytest.mark.security


@pytest.mark.asyncio
async def test_regex_masks_flat_nested_and_lists() -> None:
    r = RegexMaskRedactor(
        config=RegexMaskConfig(
            patterns=[
                r"user\.password",
                r"payment\.card\.(number|cvv)",
                r"items\.value",
            ]
        )
    )

    event = {
        "user": {"password": "secret", "name": "a"},
        "payment": {"card": {"number": "4111", "brand": "V"}},
        "items": [
            {"value": 1},
            {"value": 2},
        ],
    }

    out = await r.redact(event)
    assert out["user"]["password"] == "***"
    assert out["payment"]["card"]["number"] == "***"
    assert [x["value"] for x in out["items"]] == ["***", "***"]
    # Preserve unrelated fields
    assert out["user"]["name"] == "a"
    assert out["payment"]["card"]["brand"] == "V"


@pytest.mark.asyncio
async def test_idempotent_and_absent_paths_regex() -> None:
    r = RegexMaskRedactor(
        config=RegexMaskConfig(
            patterns=[r"a\.b\.c", r"x\.y", r"already\.masked"],
        )
    )
    evt = {"a": {"b": {"c": "top"}}, "already": {"masked": "***"}}
    out1 = await r.redact(evt)
    out2 = await r.redact(out1)
    assert out1["a"]["b"]["c"] == "***"
    assert out2["a"]["b"]["c"] == "***"
    # Absent path x.y does nothing
    assert "x" not in out1
    # Already masked remains masked
    assert out2["already"]["masked"] == "***"


# ------------------------------------------------------------------
# ReDoS Protection Tests (Story 4.50)
# ------------------------------------------------------------------


def test_rejects_nested_quantifier_pattern() -> None:
    """Patterns with nested quantifiers like (a+)+ should be rejected."""
    redactor = RegexMaskRedactor(config={"patterns": [r"(a+)+"]})
    assert redactor._pattern_errors, "Should reject nested quantifier pattern"
    assert "nested quantifier" in redactor._pattern_errors[0].lower()


def test_rejects_overlapping_alternation_pattern() -> None:
    """Patterns with alternation + quantifier like (a|a)+ should be rejected."""
    redactor = RegexMaskRedactor(config={"patterns": [r"(a|aa)+"]})
    assert redactor._pattern_errors, "Should reject overlapping alternation pattern"
    assert "alternation" in redactor._pattern_errors[0].lower()


def test_rejects_wildcard_bounded_repetition() -> None:
    """Patterns with wildcard in bounded repetition like (.*a){10,} should be rejected."""
    redactor = RegexMaskRedactor(config={"patterns": [r"(.*a){10,}"]})
    assert redactor._pattern_errors, "Should reject wildcard bounded repetition pattern"
    assert "bounded repetition" in redactor._pattern_errors[0].lower()


@pytest.mark.parametrize(
    "pattern",
    [
        r"user\.email",  # Literal path
        r"user\..*\.secret",  # Simple wildcard
        r"request\.headers\.[^.]+",  # Character class (no nesting)
        r"(password|secret|token)",  # Simple alternation without quantifier
    ],
    ids=["literal", "wildcard", "char_class", "alternation_no_quantifier"],
)
def test_accepts_safe_patterns(pattern: str) -> None:
    """Common safe patterns for field path matching should be accepted."""
    redactor = RegexMaskRedactor(config={"patterns": [pattern]})
    assert not redactor._pattern_errors, f"Should accept safe pattern: {pattern}"


@pytest.mark.asyncio
async def test_health_check_fails_on_dangerous_pattern() -> None:
    """health_check() should return False if any patterns were rejected."""
    redactor = RegexMaskRedactor(config={"patterns": [r"(a+)+"]})
    assert await redactor.health_check() is False


def test_allow_unsafe_patterns_bypasses_validation() -> None:
    """allow_unsafe_patterns=True should bypass ReDoS validation."""
    redactor = RegexMaskRedactor(
        config={
            "patterns": [r"(a+)+"],
            "allow_unsafe_patterns": True,
        }
    )
    assert not redactor._pattern_errors, "Should allow unsafe pattern with escape hatch"


@pytest.mark.asyncio
async def test_guardrails_depth_and_scan_limits_regex(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Deeply nested dict to challenge guardrails
    deep: dict[str, object] = {}
    cur: dict[str, object] = deep
    for _i in range(50):
        nxt: dict[str, object] = {}
        cur["k"] = nxt
        cur = nxt

    r = RegexMaskRedactor(
        config=RegexMaskConfig(
            patterns=[r"k(\.k){9}"],  # equivalent depth to trip limits
            max_depth=5,
            max_keys_scanned=5,
        )
    )

    out = await r.redact(deep)
    # No crash and shape preserved
    assert isinstance(out, dict)
