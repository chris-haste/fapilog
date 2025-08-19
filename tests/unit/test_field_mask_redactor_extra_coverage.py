from __future__ import annotations

import pytest

from fapilog.plugins.redactors.field_mask import (
    FieldMaskConfig,
    FieldMaskRedactor,
)


@pytest.mark.asyncio
async def test_mask_simple_and_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    red = FieldMaskRedactor(
        config=FieldMaskConfig(fields_to_mask=["user.password"], mask_string="***")
    )
    e = {"user": {"password": "secret", "other": 1}}
    out = await red.redact(e)
    assert out["user"]["password"] == "***"
    # Idempotent mask
    e2 = {"user": {"password": "***"}}
    out2 = await red.redact(e2)
    assert out2["user"]["password"] == "***"


@pytest.mark.asyncio
async def test_wildcard_dict_terminal() -> None:
    red = FieldMaskRedactor(config=FieldMaskConfig(fields_to_mask=["*"]))
    out = await red.redact({"a": 1, "b": "x"})
    assert out == {"a": "***", "b": "***"}


@pytest.mark.asyncio
async def test_wildcard_list_under_key_terminal() -> None:
    red = FieldMaskRedactor(config=FieldMaskConfig(fields_to_mask=["users[*]"]))
    out = await red.redact({"users": ["a", "b", "c"]})
    assert out["users"] == ["***", "***", "***"]


@pytest.mark.asyncio
async def test_wildcard_list_descend_and_numeric_index() -> None:
    red = FieldMaskRedactor(
        config=FieldMaskConfig(fields_to_mask=["users[*].token", "users.1.token"])
    )
    out = await red.redact({"users": [{"token": "x"}, {"token": "y"}, {"token": "z"}]})
    assert out["users"][0]["token"] == "***"
    assert out["users"][1]["token"] == "***"
    assert out["users"][2]["token"] == "***"


@pytest.mark.asyncio
async def test_numeric_index_ignored_on_dict() -> None:
    red = FieldMaskRedactor(config=FieldMaskConfig(fields_to_mask=["a.0.b"]))
    out = await red.redact({"a": {"0": {"b": "keep"}}})
    # Path '0' treated as index for dict -> ignored, value unchanged
    assert out["a"]["0"]["b"] == "keep"


@pytest.mark.asyncio
async def test_max_depth_exceeded_warn(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict] = []

    def _warn(_component: str, _msg: str, **kw) -> None:  # type: ignore[no-untyped-def]
        captured.append({"component": _component, "msg": _msg, **kw})

    monkeypatch.setattr(
        "fapilog.plugins.redactors.field_mask.diagnostics.warn",
        _warn,
        raising=True,
    )
    red = FieldMaskRedactor(
        config=FieldMaskConfig(fields_to_mask=["a.b.c"], max_depth=1)
    )
    await red.redact({"a": {"b": {"c": "v"}}})
    assert any("max depth" in w["msg"] for w in captured)


@pytest.mark.asyncio
async def test_max_keys_scanned_exceeded_warn(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict] = []

    def _warn(_component: str, _msg: str, **kw) -> None:  # type: ignore[no-untyped-def]
        captured.append({"component": _component, "msg": _msg, **kw})

    monkeypatch.setattr(
        "fapilog.plugins.redactors.field_mask.diagnostics.warn",
        _warn,
        raising=True,
    )
    # Many nested dicts so traversal re-enters and checks scanned limit often
    payload = {f"k{i}": {"x": i} for i in range(10)}
    red = FieldMaskRedactor(
        config=FieldMaskConfig(fields_to_mask=["*.x"], max_keys_scanned=2)
    )
    await red.redact(payload)
    assert any("max keys" in w["msg"] for w in captured)


class _RaiseOnSet(dict):
    def __setitem__(self, key, value):  # type: ignore[no-untyped-def]
        raise RuntimeError("nope")


@pytest.mark.asyncio
async def test_block_on_unredactable_terminal_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict] = []

    def _warn(_component: str, _msg: str, **kw) -> None:  # type: ignore[no-untyped-def]
        captured.append({"component": _component, "msg": _msg, **kw})

    monkeypatch.setattr(
        "fapilog.plugins.redactors.field_mask.diagnostics.warn",
        _warn,
        raising=True,
    )
    nested = _RaiseOnSet({"a": "x"})
    red = FieldMaskRedactor(
        config=FieldMaskConfig(fields_to_mask=["nested.a"], block_on_unredactable=True)
    )
    await red.redact({"nested": nested})
    assert any("unredactable terminal" in w["msg"] for w in captured)


@pytest.mark.asyncio
async def test_block_on_unredactable_intermediate_and_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict] = []

    def _warn(_component: str, _msg: str, **kw) -> None:  # type: ignore[no-untyped-def]
        captured.append({"component": _component, "msg": _msg, **kw})

    monkeypatch.setattr(
        "fapilog.plugins.redactors.field_mask.diagnostics.warn",
        _warn,
        raising=True,
    )
    red = FieldMaskRedactor(
        config=FieldMaskConfig(
            fields_to_mask=["a.b", "lst.x"], block_on_unredactable=True
        )
    )
    # Intermediate non-container for a.b
    await red.redact({"a": 1})
    # List default propagation hits primitive items for lst.x
    await red.redact({"lst": [1, 2, 3]})
    msgs = " ".join(w["msg"] for w in captured)
    assert "unredactable intermediate" in msgs
    assert "unredactable container" in msgs
