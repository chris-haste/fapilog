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
            # Databases (Story 4.74)
            (
                "postgres",
                "postgres://admin:s3cret@db.prod:5432/app",
                "postgres://db.prod:5432/app",
            ),
            (
                "postgresql",
                "postgresql://u:p@host/db",
                "postgresql://host/db",
            ),
            (
                "mysql",
                "mysql://root:pw@localhost:3306/mydb",
                "mysql://localhost:3306/mydb",
            ),
            (
                "mongodb",
                "mongodb://user:pass@cluster0.abc.mongodb.net/db",
                "mongodb://cluster0.abc.mongodb.net/db",
            ),
            (
                "mongodb+srv",
                "mongodb+srv://user:pass@cluster0.abc.mongodb.net/db",
                "mongodb+srv://cluster0.abc.mongodb.net/db",
            ),
            (
                "mssql",
                "mssql://sa:pw@sqlserver.local/master",
                "mssql://sqlserver.local/master",
            ),
            (
                "cockroachdb",
                "cockroachdb://root:pw@crdb:26257/bank",
                "cockroachdb://crdb:26257/bank",
            ),
            # Caches / Message Brokers (Story 4.74)
            (
                "redis",
                "redis://default:pw@redis.prod:6379/0",
                "redis://redis.prod:6379/0",
            ),
            (
                "rediss",
                "rediss://default:pw@redis.prod:6380/0",
                "rediss://redis.prod:6380/0",
            ),
            (
                "amqp",
                "amqp://guest:guest@rabbit:5672/vhost",
                "amqp://rabbit:5672/vhost",
            ),
            (
                "amqps",
                "amqps://user:pw@broker:5671/",
                "amqps://broker:5671/",
            ),
            (
                "nats",
                "nats://token:secret@nats.prod:4222",
                "nats://nats.prod:4222",
            ),
            # Directory / Mail (Story 4.74)
            (
                "ldap",
                "ldap://cn=admin:pw@ldap.corp:389/dc=corp",
                "ldap://ldap.corp:389/dc=corp",
            ),
            (
                "ldaps",
                "ldaps://cn=admin:pw@ldap.corp:636/dc=corp",
                "ldaps://ldap.corp:636/dc=corp",
            ),
            (
                "smtp",
                "smtp://relay:pw@mail.corp:587/",
                "smtp://mail.corp:587/",
            ),
            (
                "smtps",
                "smtps://relay:pw@mail.corp:465/",
                "smtps://mail.corp:465/",
            ),
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
            # Infrastructure schemes without credentials (Story 4.74)
            "postgres://db.prod:5432/app",
            "redis://redis.prod:6379/0",
            "amqp://rabbit:5672/vhost",
            "mongodb://cluster0.abc.mongodb.net/db",
            "mysql://localhost:3306/mydb",
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
            # Web / VCS
            "http://",
            "https://",
            "ftp://",
            "ftps://",
            "ssh://",
            "git://",
            "svn://",
            "//",
            # Databases (Story 4.74)
            "postgres://",
            "postgresql://",
            "mysql://",
            "mongodb://",
            "mongodb+srv://",
            "mssql://",
            "cockroachdb://",
            # Caches / Message Brokers (Story 4.74)
            "redis://",
            "rediss://",
            "amqp://",
            "amqps://",
            "nats://",
            # Directory / Mail (Story 4.74)
            "ldap://",
            "ldaps://",
            "smtp://",
            "smtps://",
        )
        for scheme in required_schemes:
            assert scheme in _URL_SCHEMES, f"Missing scheme: {scheme}"


class TestCoreGuardrails:
    """Tests for core guardrail enforcement (Story 4.65)."""

    @pytest.mark.asyncio
    async def test_core_max_depth_limits_traversal(self) -> None:
        """URLs beyond core_max_depth should not be scrubbed."""
        r = UrlCredentialsRedactor(core_max_depth=2)
        # depth 0=root dict, recurse into a at depth 1, into b at depth 2,
        # into c at depth 3 → 3 > 2, so c's contents are not processed
        event = {"a": {"b": {"c": {"u": "https://user:pass@host.com"}}}}
        result = await r.redact(event)
        assert result["a"]["b"]["c"]["u"] == "https://user:pass@host.com"

    @pytest.mark.asyncio
    async def test_core_max_depth_allows_within_limit(self) -> None:
        """URLs within core_max_depth should be scrubbed."""
        r = UrlCredentialsRedactor(core_max_depth=2)
        # depth 0=root dict, a.u at depth 1 → within limit, scrubbed
        event = {"a": {"u": "https://user:pass@host.com/path"}}
        result = await r.redact(event)
        assert result["a"]["u"] == "https://host.com/path"

    @pytest.mark.asyncio
    async def test_core_max_keys_scanned_limits_traversal(self) -> None:
        """After scanning core_max_keys_scanned keys, stop traversing."""
        r = UrlCredentialsRedactor(core_max_keys_scanned=2)
        # First dict scans keys; after scanned exceeds 2, nested dicts stop
        # Root dict processes k1 (scanned=1), k2 (scanned=2), nested (scanned=3)
        # but nested recurses and at entry scanned=3 > 2 → stops
        event = {
            "k1": "plain",
            "k2": "plain",
            "nested": {"u": "https://user:pass@host.com/path"},
        }
        result = await r.redact(event)
        assert result["nested"]["u"] == "https://user:pass@host.com/path"

    @pytest.mark.asyncio
    async def test_defaults_without_core_override(self) -> None:
        """Without core overrides, plugin defaults (depth 16, scanned 1000) apply."""
        r = UrlCredentialsRedactor()
        # Shallow URL should still be scrubbed with defaults
        event = {"u": "https://user:pass@host.com/path"}
        result = await r.redact(event)
        assert result["u"] == "https://host.com/path"

    @pytest.mark.asyncio
    async def test_more_restrictive_wins_when_core_is_higher(self) -> None:
        """If core limit is higher than plugin default, plugin default wins."""
        r = UrlCredentialsRedactor(core_max_depth=100)
        # Plugin default is 16, so 16 should still be effective
        assert r._max_depth == 16

    @pytest.mark.asyncio
    async def test_more_restrictive_wins_when_core_is_lower(self) -> None:
        """If core limit is lower than plugin default, core wins."""
        r = UrlCredentialsRedactor(core_max_depth=3, core_max_keys_scanned=50)
        assert r._max_depth == 3
        assert r._max_scanned == 50
