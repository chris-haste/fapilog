from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fapilog.plugins.redactors.field_mask import FieldMaskRedactor

pytestmark = pytest.mark.property

_sensitive_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

sensitive_values = st.text(alphabet=_sensitive_chars, min_size=1, max_size=40).filter(
    lambda value: value != "***"
)

sensitive_field_names = st.sampled_from(
    [
        "password",
        "secret",
        "api_key",
        "token",
        "credential",
        "ssn",
        "credit_card",
        "private_key",
        "auth",
    ]
)

path_segment = st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=8)


@pytest.mark.asyncio
@given(secret_value=sensitive_values, field_name=sensitive_field_names)
async def test_sensitive_value_never_in_output(
    secret_value: str, field_name: str
) -> None:
    redactor = FieldMaskRedactor(config={"fields_to_mask": [field_name]})
    event = {field_name: secret_value}

    redacted = await redactor.redact(event)

    assert redacted[field_name] == "***"


@pytest.mark.asyncio
@given(
    secret_value=sensitive_values,
    nesting_path=st.lists(path_segment, min_size=1, max_size=4),
)
async def test_nested_secrets_redacted(
    secret_value: str, nesting_path: list[str]
) -> None:
    full_path = ".".join([*nesting_path, "password"])
    redactor = FieldMaskRedactor(config={"fields_to_mask": [full_path]})

    event: dict[str, object] = {"message": "test"}
    current: dict[str, object] = event
    for segment in nesting_path:
        nxt: dict[str, object] = {}
        current[segment] = nxt
        current = nxt
    current["password"] = secret_value

    redacted = await redactor.redact(event)

    cursor: dict[str, object] = redacted
    for segment in nesting_path:
        next_cursor = cursor[segment]
        assert isinstance(next_cursor, dict)
        cursor = next_cursor

    assert cursor["password"] == "***"
