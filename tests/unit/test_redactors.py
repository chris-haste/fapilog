from __future__ import annotations

import pytest

from fapilog.plugins.redactors.field_mask import (
    FieldMaskConfig,
    FieldMaskRedactor,
)

pytestmark = pytest.mark.security


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


@pytest.mark.asyncio
async def test_drop_guardrail_returns_dict_not_none() -> None:
    """AC1/AC2: When on_guardrail_exceeded='drop' triggers, redact() returns
    the original event as a dict — never None."""
    r = FieldMaskRedactor(
        config=FieldMaskConfig(
            fields_to_mask=["a.b.c.d.e.f.g"],
            max_depth=2,
            on_guardrail_exceeded="drop",
        )
    )
    event = {"a": {"b": {"c": {"d": {"e": {"f": {"g": "secret"}}}}}}}
    result = await r.redact(event)
    assert result is not None, "redact() must never return None"  # noqa: WA003
    assert isinstance(result, dict)
    # Original event returned unchanged — guardrail prevented masking
    assert result == event


@pytest.mark.asyncio
async def test_redact_in_order_with_drop_guardrail() -> None:
    """AC3: redact_in_order preserves event when drop guardrail fires."""
    from fapilog.plugins.redactors import redact_in_order

    r = FieldMaskRedactor(
        config=FieldMaskConfig(
            fields_to_mask=["deep.nested.path.to.secret"],
            max_depth=2,
            on_guardrail_exceeded="drop",
        )
    )
    event = {"deep": {"nested": {"path": {"to": {"secret": "value"}}}}, "keep": "me"}
    result = await redact_in_order(event, [r])
    assert isinstance(result, dict)
    # The event should pass through with original data intact
    assert result["keep"] == "me"
    assert result["deep"]["nested"]["path"]["to"]["secret"] == "value"


@pytest.mark.asyncio
async def test_drop_guardrail_returns_original_not_partial() -> None:
    """When drop fires mid-way through fields, return original — not partially
    masked copy."""
    r = FieldMaskRedactor(
        config=FieldMaskConfig(
            fields_to_mask=["shallow", "a.b.c.d.e.f.g"],
            max_depth=2,
            on_guardrail_exceeded="drop",
        )
    )
    event = {
        "shallow": "visible",
        "a": {"b": {"c": {"d": {"e": {"f": {"g": "secret"}}}}}},
    }
    result = await r.redact(event)
    assert isinstance(result, dict)
    # Must return original event, NOT the partially-masked copy
    assert result["shallow"] == "visible"


@pytest.mark.asyncio
async def test_snapshot_preserved_on_redactor_exception() -> None:
    """AC1: When a redactor partially mutates nested data then raises,
    the last good snapshot must remain unchanged."""
    from fapilog.plugins.redactors import redact_in_order

    class PartialMutatingRedactor:
        name = "partial_mutator"

        async def start(self) -> None:
            pass

        async def stop(self) -> None:
            pass

        async def health_check(self) -> bool:
            return True

        async def redact(self, event: dict) -> dict:
            event["user"]["name"] = "***"
            raise RuntimeError("boom")

    event = {"user": {"name": "Alice", "role": "admin"}}
    result = await redact_in_order(event, [PartialMutatingRedactor()])
    assert result["user"]["name"] == "Alice"
    assert result["user"]["role"] == "admin"


@pytest.mark.asyncio
async def test_nested_snapshot_not_corrupted_by_partial_mutation() -> None:
    """Deep nesting variant: mutations at multiple levels must not leak."""
    from fapilog.plugins.redactors import redact_in_order

    class DeepMutatingRedactor:
        name = "deep_mutator"

        async def start(self) -> None:
            pass

        async def stop(self) -> None:
            pass

        async def health_check(self) -> bool:
            return True

        async def redact(self, event: dict) -> dict:
            event["a"]["b"]["c"] = "CORRUPTED"
            event["a"]["x"] = "INJECTED"
            raise RuntimeError("deep boom")

    event = {"a": {"b": {"c": "original"}, "x": "keep"}, "top": "safe"}
    result = await redact_in_order(event, [DeepMutatingRedactor()])
    assert result["a"]["b"]["c"] == "original"
    assert result["a"]["x"] == "keep"
    assert result["top"] == "safe"


@pytest.mark.asyncio
async def test_contract_redact_in_order_with_pipeline_redactors() -> None:
    """AC3: Real redactors chained through redact_in_order produce valid output."""
    from fapilog.plugins.redactors import redact_in_order

    redactor = FieldMaskRedactor(config={"fields_to_mask": ["data.password"]})
    event = {"data": {"password": "secret", "name": "Alice"}}
    result = await redact_in_order(event, [redactor])
    assert isinstance(result, dict)
    assert result["data"]["password"] == "***"
    assert result["data"]["name"] == "Alice"
