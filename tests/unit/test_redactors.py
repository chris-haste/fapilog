from __future__ import annotations

import pytest

from fapilog.plugins.redactors.field_mask import (
    FieldMaskConfig,
    FieldMaskRedactor,
)


@pytest.mark.asyncio
async def test_masks_flat_and_nested_and_lists() -> None:
    r = FieldMaskRedactor(
        config=FieldMaskConfig(
            fields_to_mask=[
                "user.password",
                "payment.card.number",
                "items[*].value",
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
    # Preserve shape and unrelated fields
    assert out["user"]["name"] == "a"
    assert out["payment"]["card"]["brand"] == "V"


@pytest.mark.asyncio
async def test_idempotent_and_absent_paths() -> None:
    r = FieldMaskRedactor(
        config=FieldMaskConfig(fields_to_mask=["a.b.c", "x.y", "already.masked"])
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
async def test_guardrails_depth_and_scan_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Create a deeply nested structure to trip depth and scan counters
    deep: dict[str, object] = {}
    cur: dict[str, object] = deep
    for _i in range(50):
        nxt: dict[str, object] = {}
        cur["k"] = nxt
        cur = nxt
    r = FieldMaskRedactor(
        config=FieldMaskConfig(
            fields_to_mask=[
                "k.k.k.k.k.k.k.k.k.k",
            ],
            max_depth=5,
            max_keys_scanned=5,
        )
    )
    out = await r.redact(deep)
    # No crash and shape preserved
    assert isinstance(out, dict)
