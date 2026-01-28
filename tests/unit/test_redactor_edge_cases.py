from __future__ import annotations

import pytest

from fapilog.plugins.redactors.field_mask import (
    FieldMaskConfig,
    FieldMaskRedactor,
)

pytestmark = pytest.mark.security


@pytest.mark.asyncio
async def test_mask_simple_and_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    red = FieldMaskRedactor(
        config=FieldMaskConfig(fields_to_mask=["user.password"], mask_string="***")
    )
    e = {"user": {"password": "secret", "other": 1}}
    out = await red.redact(e)
    assert out is not None  # noqa: WA003
    assert out["user"]["password"] == "***"
    # Idempotent mask
    e2 = {"user": {"password": "***"}}
    out2 = await red.redact(e2)
    assert out2 is not None  # noqa: WA003
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
    assert out is not None  # noqa: WA003
    assert out["users"] == ["***", "***", "***"]


@pytest.mark.asyncio
async def test_wildcard_list_descend_and_numeric_index() -> None:
    red = FieldMaskRedactor(
        config=FieldMaskConfig(fields_to_mask=["users[*].token", "users.1.token"])
    )
    out = await red.redact({"users": [{"token": "x"}, {"token": "y"}, {"token": "z"}]})
    assert out is not None  # noqa: WA003
    assert out["users"][0]["token"] == "***"
    assert out["users"][1]["token"] == "***"
    assert out["users"][2]["token"] == "***"


@pytest.mark.asyncio
async def test_numeric_index_ignored_on_dict() -> None:
    red = FieldMaskRedactor(config=FieldMaskConfig(fields_to_mask=["a.0.b"]))
    out = await red.redact({"a": {"0": {"b": "keep"}}})
    assert out is not None  # noqa: WA003
    # Path '0' treated as index for dict -> ignored, value unchanged
    assert out["a"]["0"]["b"] == "keep"


@pytest.mark.asyncio
async def test_on_guardrail_exceeded_config_option() -> None:
    """AC1: Config accepts on_guardrail_exceeded with valid modes."""
    # Default is "replace_subtree" (fail-closed, Story 4.61)
    config = FieldMaskConfig(fields_to_mask=["password"])
    assert config.on_guardrail_exceeded == "replace_subtree"

    # Explicit modes
    for mode in ("warn", "drop", "replace_subtree"):
        cfg = FieldMaskConfig(fields_to_mask=["password"], on_guardrail_exceeded=mode)
        assert cfg.on_guardrail_exceeded == mode


@pytest.mark.asyncio
async def test_max_depth_exceeded_drop_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC3: Drop mode returns None when max_depth exceeded."""
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
            fields_to_mask=["a.b.c"],
            max_depth=1,
            on_guardrail_exceeded="drop",
        )
    )
    result = await red.redact({"a": {"b": {"c": "secret"}}})
    assert result is None
    # Should still emit diagnostic
    assert any("max depth" in w["msg"] for w in captured)


@pytest.mark.asyncio
async def test_max_keys_scanned_drop_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC3: Drop mode returns None when max_keys_scanned exceeded."""
    captured: list[dict] = []

    def _warn(_component: str, _msg: str, **kw) -> None:  # type: ignore[no-untyped-def]
        captured.append({"component": _component, "msg": _msg, **kw})

    monkeypatch.setattr(
        "fapilog.plugins.redactors.field_mask.diagnostics.warn",
        _warn,
        raising=True,
    )
    payload = {f"k{i}": {"x": i} for i in range(10)}
    red = FieldMaskRedactor(
        config=FieldMaskConfig(
            fields_to_mask=["*.x"],
            max_keys_scanned=2,
            on_guardrail_exceeded="drop",
        )
    )
    result = await red.redact(payload)
    assert result is None
    # Should still emit diagnostic
    assert any("max keys" in w["msg"] for w in captured)


@pytest.mark.asyncio
async def test_max_depth_exceeded_replace_subtree_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: Replace subtree mode replaces unscanned subtree with mask."""
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
            fields_to_mask=["level1.level2.level3.password"],
            max_depth=2,
            on_guardrail_exceeded="replace_subtree",
        )
    )
    event = {"level1": {"level2": {"level3": {"password": "secret"}}}}
    result = await red.redact(event)
    # level3 and below replaced with mask at the boundary
    assert result == {"level1": {"level2": "***"}}
    # Should still emit diagnostic
    assert any("max depth" in w["msg"] for w in captured)


@pytest.mark.asyncio
async def test_max_keys_scanned_replace_subtree_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: Replace subtree mode works for max_keys_scanned guardrail."""
    captured: list[dict] = []

    def _warn(_component: str, _msg: str, **kw) -> None:  # type: ignore[no-untyped-def]
        captured.append({"component": _component, "msg": _msg, **kw})

    monkeypatch.setattr(
        "fapilog.plugins.redactors.field_mask.diagnostics.warn",
        _warn,
        raising=True,
    )
    # Wide structure with many keys
    payload = {"outer": {f"k{i}": {"secret": f"val{i}"} for i in range(10)}}
    red = FieldMaskRedactor(
        config=FieldMaskConfig(
            fields_to_mask=["outer.*.secret"],
            max_keys_scanned=3,
            on_guardrail_exceeded="replace_subtree",
        )
    )
    result = await red.redact(payload)
    # Should have replaced at least some branches with mask
    assert result is not None  # noqa: WA003
    # Should emit diagnostic
    assert any("max keys" in w["msg"] for w in captured)


@pytest.mark.asyncio
async def test_core_guardrails_override_plugin_settings() -> None:
    """Test that core guardrails (more restrictive) override plugin settings."""
    red = FieldMaskRedactor(
        config=FieldMaskConfig(
            fields_to_mask=["a.b.c.d.e"],
            max_depth=10,
            max_keys_scanned=1000,
        ),
        core_max_depth=2,
        core_max_keys_scanned=5,
    )
    # Core values should win when more restrictive
    assert red._max_depth == 2
    assert red._max_scanned == 5


@pytest.mark.asyncio
async def test_plugin_guardrails_win_when_more_restrictive() -> None:
    """Test that plugin guardrails win when more restrictive than core."""
    red = FieldMaskRedactor(
        config=FieldMaskConfig(
            fields_to_mask=["a.b"],
            max_depth=3,
            max_keys_scanned=10,
        ),
        core_max_depth=10,
        core_max_keys_scanned=100,
    )
    # Plugin values should win when more restrictive
    assert red._max_depth == 3
    assert red._max_scanned == 10


@pytest.mark.asyncio
async def test_warn_mode_default_preserves_current_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: Warn mode (default) emits warning and passes event through."""
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
            fields_to_mask=["a.b.c.d.password"],
            max_depth=2,
            # on_guardrail_exceeded defaults to "warn"
        )
    )
    event = {"a": {"b": {"c": {"d": {"password": "secret"}}}}}
    result = await red.redact(event)
    # Event passes through (not None)
    assert result is not None  # noqa: WA003
    # Event structure preserved (partial redaction only up to depth limit)
    assert "a" in result
    # Warning emitted
    assert any("max depth" in w["msg"] for w in captured)


@pytest.mark.asyncio
async def test_empty_path_segment_handled() -> None:
    """Test that empty path returns early."""
    red = FieldMaskRedactor(
        config=FieldMaskConfig(
            fields_to_mask=[""],  # Empty path
        )
    )
    event = {"a": "value"}
    result = await red.redact(event)
    assert result is not None  # noqa: WA003
    assert result == {"a": "value"}


@pytest.mark.asyncio
async def test_health_check_returns_true_for_valid_config() -> None:
    """Test health_check method."""
    red = FieldMaskRedactor(
        config=FieldMaskConfig(
            fields_to_mask=["password"],
        )
    )
    result = await red.health_check()
    assert result is True


@pytest.mark.asyncio
async def test_health_check_returns_false_for_empty_mask() -> None:
    """Test health_check fails with empty mask string."""
    red = FieldMaskRedactor(
        config=FieldMaskConfig(
            fields_to_mask=["password"],
            mask_string="",
        )
    )
    result = await red.health_check()
    assert result is False


@pytest.mark.asyncio
async def test_wildcard_terminal_non_list_ignored() -> None:
    """Test that key[*] on non-list value is treated as absent."""
    red = FieldMaskRedactor(
        config=FieldMaskConfig(
            fields_to_mask=["data[*]"],
        )
    )
    # data is a string, not a list - should be ignored
    event = {"data": "string_value"}
    result = await red.redact(event)
    assert result is not None  # noqa: WA003
    assert result == {"data": "string_value"}


@pytest.mark.asyncio
async def test_list_wildcard_traversal() -> None:
    """Test wildcard in list traversal."""
    # Test list items under a key with wildcard
    red = FieldMaskRedactor(
        config=FieldMaskConfig(
            fields_to_mask=["items.*.secret"],
        )
    )
    event = {"items": [{"secret": "s1"}, {"secret": "s2"}]}
    result = await red.redact(event)
    assert result is not None  # noqa: WA003
    assert result["items"][0]["secret"] == "***"
    assert result["items"][1]["secret"] == "***"


@pytest.mark.asyncio
async def test_list_numeric_index_traversal() -> None:
    """Test numeric index traversal in lists."""
    red = FieldMaskRedactor(
        config=FieldMaskConfig(
            fields_to_mask=["items.0.secret"],
        )
    )
    event = {"items": [{"secret": "s0"}, {"secret": "s1"}]}
    result = await red.redact(event)
    assert result is not None  # noqa: WA003
    assert result["items"][0]["secret"] == "***"
    assert result["items"][1]["secret"] == "s1"


@pytest.mark.asyncio
async def test_depth_exceeded_via_list_traversal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test depth exceeded when traversing lists deeply."""
    captured: list[dict] = []

    def _warn(_component: str, _msg: str, **kw) -> None:  # type: ignore[no-untyped-def]
        captured.append({"component": _component, "msg": _msg, **kw})

    monkeypatch.setattr(
        "fapilog.plugins.redactors.field_mask.diagnostics.warn",
        _warn,
        raising=True,
    )
    # List traversal increments depth
    red = FieldMaskRedactor(
        config=FieldMaskConfig(
            fields_to_mask=["items.secret"],
            max_depth=1,
        )
    )
    # Nested list that exceeds depth
    event = {"items": [[{"secret": "deep"}]]}
    result = await red.redact(event)
    assert result is not None  # noqa: WA003
    # Should have warning due to depth
    assert any("max depth" in w["msg"] for w in captured)


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
