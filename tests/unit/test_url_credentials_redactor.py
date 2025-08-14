from __future__ import annotations

import pytest

from fapilog.plugins.redactors.url_credentials import UrlCredentialsRedactor


@pytest.mark.asyncio
async def test_url_credentials_stripping_basic() -> None:
    r = UrlCredentialsRedactor()
    event = {
        "a": "https://user:pass@example.com/x?y=1#z",
        "b": "not a url",
        "nested": {"u": "http://alice:secret@host/path"},
        "list": ["http://bob:pw@h/", {"m": "https://no-creds.example/x"}],
    }
    out = await r.redact(event)
    assert out["a"].startswith("https://example.com/")
    assert out["b"] == "not a url"
    assert out["nested"]["u"].startswith("http://host/")
    assert out["list"][0].startswith("http://h/")
    assert out["list"][1]["m"].startswith("https://no-creds.example/")


@pytest.mark.asyncio
async def test_url_credentials_idempotent_and_guardrails() -> None:
    r = UrlCredentialsRedactor()
    # Already stripped
    event = {"u": "https://example.com/x"}
    out = await r.redact(event)
    assert out["u"] == "https://example.com/x"
    # Overly long strings should be left as-is
    long = "a" * 5000
    out2 = await r.redact({"s": long})
    assert out2["s"] == long
