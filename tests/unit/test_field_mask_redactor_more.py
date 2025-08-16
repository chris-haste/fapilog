from __future__ import annotations

import pytest

from fapilog.core.diagnostics import set_writer_for_tests
from fapilog.plugins.redactors.field_mask import (
    PLUGIN_METADATA,
    FieldMaskConfig,
    FieldMaskRedactor,
)


@pytest.mark.asyncio
async def test_block_on_unredactable_intermediate_emits_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Capture diagnostics
    diags: list[dict[str, object]] = []

    def _writer(payload: dict[str, object]) -> None:
        diags.append(payload)

    set_writer_for_tests(_writer)

    # Force diagnostics enabled
    import fapilog.core.diagnostics as _diag_mod

    monkeypatch.setattr(_diag_mod, "_is_enabled", lambda: True)

    r = FieldMaskRedactor(
        config=FieldMaskConfig(
            fields_to_mask=["a.b.c"],
            block_on_unredactable=True,
        )
    )
    event = {"a": 5}
    out = await r.redact(event)
    assert isinstance(out, dict)

    # Verify diagnostics contains redactor warning about unredactable field
    assert any(
        (d.get("component") == "redactor")
        and ("unredactable intermediate field" in str(d.get("message", "")))
        and (d.get("path") == "a.b.c")
        for d in diags
    )


@pytest.mark.asyncio
async def test_masks_non_string_values_to_mask_string() -> None:
    r = FieldMaskRedactor(
        config=FieldMaskConfig(fields_to_mask=["a.b"], mask_string="XXX"),
    )
    evt = {"a": {"b": 123}}
    out = await r.redact(evt)
    assert out["a"]["b"] == "XXX"
    assert isinstance(out["a"]["b"], str)


@pytest.mark.asyncio
async def test_masks_within_nested_lists() -> None:
    r = FieldMaskRedactor(
        config=FieldMaskConfig(
            fields_to_mask=["users[*].email", "users[*].profile.email"],
        )
    )
    evt = {
        "users": [
            {"email": "u1@example.com"},
            {"profile": {"email": "u2@example.com"}},
        ]
    }
    out = await r.redact(evt)
    assert out["users"][0]["email"] == "***"
    assert out["users"][1]["profile"]["email"] == "***"


@pytest.mark.asyncio
async def test_masks_with_numeric_index_in_lists() -> None:
    r = FieldMaskRedactor(
        config=FieldMaskConfig(
            fields_to_mask=["users.1.profile.email"],
        )
    )
    evt = {
        "users": [
            {"profile": {"email": "u0@example.com"}},
            {"profile": {"email": "u1@example.com"}},
        ]
    }
    out = await r.redact(evt)
    assert out["users"][0]["profile"]["email"] == "u0@example.com"
    assert out["users"][1]["profile"]["email"] == "***"


@pytest.mark.asyncio
async def test_guardrails_emit_warnings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Capture diagnostics
    diags: list[dict[str, object]] = []

    def _writer(payload: dict[str, object]) -> None:
        diags.append(payload)

    set_writer_for_tests(_writer)

    # Force diagnostics enabled
    import fapilog.core.diagnostics as _diag_mod

    monkeypatch.setattr(_diag_mod, "_is_enabled", lambda: True)

    # Deep structure to exceed depth
    deep: dict[str, object] = {}
    cur: dict[str, object] = deep
    for _i in range(30):
        nxt: dict[str, object] = {}
        cur["k"] = nxt
        cur = nxt

    # Wide scan via list traversal to exceed scan count
    many_list: dict[str, object] = {"arr": [{"value": i} for i in range(50)]}

    r1 = FieldMaskRedactor(
        config=FieldMaskConfig(
            fields_to_mask=["k.k.k.k.k.k"],
            max_depth=3,
        ),
    )
    r2 = FieldMaskRedactor(
        config=FieldMaskConfig(
            fields_to_mask=["arr.value"],
            max_keys_scanned=5,
        )
    )

    _ = await r1.redact(deep)
    _ = await r2.redact(many_list)

    has_depth = any(
        (d.get("component") == "redactor")
        and ("max depth exceeded" in str(d.get("message", "")))
        for d in diags
    )
    has_scan = any(
        (d.get("component") == "redactor")
        and ("max keys scanned exceeded" in str(d.get("message", "")))
        for d in diags
    )
    assert has_depth and has_scan


def test_name_and_plugin_metadata_present() -> None:
    assert FieldMaskRedactor.name == "field-mask"
    assert isinstance(PLUGIN_METADATA, dict)
    assert PLUGIN_METADATA.get("name") == "field-mask"
    assert PLUGIN_METADATA.get("plugin_type") == "redactor"
