from __future__ import annotations

import pytest

from fapilog.plugins.redactors.url_credentials import (
    _URL_SCHEMES,
    UrlCredentialsRedactor,
)

pytestmark = pytest.mark.security


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


class TestUrlSchemeOptimization:
    """Tests for URL scheme prefix check optimization (Story 1.41)."""

    def test_non_url_strings_returned_unchanged(self) -> None:
        """Non-URL strings should skip urlsplit() and return unchanged."""
        r = UrlCredentialsRedactor()

        # Plain text - no URL scheme
        assert r._scrub_string("hello world") == "hello world"
        assert r._scrub_string("not a url") == "not a url"

        # File paths - no credentials possible
        assert r._scrub_string("/path/to/file") == "/path/to/file"
        assert r._scrub_string("./relative/path") == "./relative/path"

        # Email-like strings
        assert r._scrub_string("user@example.com") == "user@example.com"

        # JSON-like content
        assert r._scrub_string('{"key": "value"}') == '{"key": "value"}'

    @pytest.mark.parametrize(
        "scheme,url,expected",
        [
            # http/https with credentials - should be scrubbed
            ("http", "http://user:pass@host.com/path", "http://host.com/path"),
            ("https", "https://user:pass@host.com/path", "https://host.com/path"),
            # ftp/ftps with credentials
            ("ftp", "ftp://user:pass@files.example.com/", "ftp://files.example.com/"),
            (
                "ftps",
                "ftps://user:pass@secure.example.com/",
                "ftps://secure.example.com/",
            ),
            # ssh/git/svn with credentials
            ("ssh", "ssh://git:token@github.com/repo", "ssh://github.com/repo"),
            (
                "git",
                "git://user:pass@git.example.com/repo.git",
                "git://git.example.com/repo.git",
            ),
            (
                "svn",
                "svn://user:pass@svn.example.com/trunk",
                "svn://svn.example.com/trunk",
            ),
            # Protocol-relative URLs
            ("//", "//user:pass@cdn.example.com/asset", "//cdn.example.com/asset"),
        ],
    )
    def test_url_schemes_trigger_parsing(
        self, scheme: str, url: str, expected: str
    ) -> None:
        """URLs with credential-bearing schemes should be parsed and scrubbed."""
        r = UrlCredentialsRedactor()
        assert r._scrub_string(url) == expected

    @pytest.mark.parametrize(
        "url",
        [
            "http://example.com/path",
            "https://example.com:8080/path?query=1",
            "ftp://files.example.com/",
            "ssh://github.com/repo",
        ],
    )
    def test_urls_without_credentials_unchanged(self, url: str) -> None:
        """URLs without credentials should pass through unchanged."""
        r = UrlCredentialsRedactor()
        assert r._scrub_string(url) == url

    def test_empty_and_oversized_strings_skipped(self) -> None:
        """Empty strings and strings exceeding max length should be unchanged."""
        r = UrlCredentialsRedactor()

        # Empty string
        assert r._scrub_string("") == ""

        # Oversized string (default max is 4096)
        oversized = "https://user:pass@" + "x" * 5000
        assert r._scrub_string(oversized) == oversized

    def test_protocol_relative_urls_parsed(self) -> None:
        """Protocol-relative URLs (//) should be parsed for credentials."""
        r = UrlCredentialsRedactor()

        # With credentials - should be scrubbed
        result = r._scrub_string("//user:pass@cdn.example.com/asset.js")
        assert result == "//cdn.example.com/asset.js"

        # Without credentials - unchanged
        assert (
            r._scrub_string("//cdn.example.com/asset.js")
            == "//cdn.example.com/asset.js"
        )

    def test_url_schemes_constant_contains_required_schemes(self) -> None:
        """The _URL_SCHEMES constant should contain all credential-bearing schemes."""
        required_schemes = (
            "http://",
            "https://",
            "ftp://",
            "ftps://",
            "ssh://",
            "git://",
            "svn://",
            "//",
        )
        for scheme in required_schemes:
            assert scheme in _URL_SCHEMES, f"Missing scheme: {scheme}"
