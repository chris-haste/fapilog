from __future__ import annotations

import pytest

from fapilog.plugins.redactors.regex_mask import (
    RegexMaskConfig,
    RegexMaskRedactor,
)


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
