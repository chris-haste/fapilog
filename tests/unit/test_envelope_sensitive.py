"""Unit tests for sensitive container auto-redaction in build_envelope.

Story 4.68: sensitive= and pii= keywords are extracted from extra,
merged into data.sensitive, and recursively masked at envelope
construction time.
"""

from __future__ import annotations

from fapilog.core.envelope import build_envelope


class TestSensitiveMasking:
    """AC1: sensitive= routes to data.sensitive and values are masked."""

    def test_sensitive_values_masked(self) -> None:
        envelope = build_envelope(
            level="INFO",
            message="signup",
            extra={"sensitive": {"email": "alice@example.com", "ssn": "123-45-6789"}},
        )
        assert envelope["data"]["sensitive"]["email"] == "***"
        assert envelope["data"]["sensitive"]["ssn"] == "***"


class TestPiiAlias:
    """AC2: pii= is an alias for sensitive=."""

    def test_pii_alias_routes_to_sensitive(self) -> None:
        envelope = build_envelope(
            level="INFO",
            message="signup",
            extra={"pii": {"email": "alice@example.com"}},
        )
        assert envelope["data"]["sensitive"]["email"] == "***"
        assert "pii" not in envelope["data"]


class TestSensitiveAndPiiCombined:
    """AC3: Both sensitive= and pii= merge into data.sensitive."""

    def test_sensitive_and_pii_merged(self) -> None:
        envelope = build_envelope(
            level="INFO",
            message="signup",
            extra={
                "sensitive": {"email": "alice@example.com"},
                "pii": {"ssn": "123-45-6789"},
            },
        )
        assert envelope["data"]["sensitive"]["email"] == "***"
        assert envelope["data"]["sensitive"]["ssn"] == "***"


class TestOverlappingKeys:
    """AC4: Overlapping keys between sensitive= and pii= - pii wins."""

    def test_sensitive_and_pii_overlapping_keys(self) -> None:
        envelope = build_envelope(
            level="INFO",
            message="signup",
            extra={
                "sensitive": {"email": "alice@example.com"},
                "pii": {"email": "bob@example.com"},
            },
        )
        # Both are masked, so output is the same regardless of which wins
        assert envelope["data"]["sensitive"]["email"] == "***"
        assert "pii" not in envelope["data"]


class TestNestedSensitive:
    """AC5: Nested dicts are recursively masked."""

    def test_nested_sensitive_recursively_masked(self) -> None:
        envelope = build_envelope(
            level="INFO",
            message="payment",
            extra={
                "sensitive": {
                    "card": {"number": "4111-1111-1111-1111", "cvv": "123"},
                }
            },
        )
        assert envelope["data"]["sensitive"]["card"]["number"] == "***"
        assert envelope["data"]["sensitive"]["card"]["cvv"] == "***"

    def test_lists_in_sensitive_are_masked(self) -> None:
        envelope = build_envelope(
            level="INFO",
            message="event",
            extra={"sensitive": {"tags": ["secret1", "secret2"]}},
        )
        assert envelope["data"]["sensitive"]["tags"] == ["***", "***"]


class TestNonSensitiveUnaffected:
    """AC6: Non-sensitive fields pass through unchanged."""

    def test_non_sensitive_fields_unchanged(self) -> None:
        envelope = build_envelope(
            level="INFO",
            message="signup",
            extra={"user_role": "admin", "sensitive": {"email": "alice@example.com"}},
        )
        assert envelope["data"]["user_role"] == "admin"
        assert envelope["data"]["sensitive"]["email"] == "***"


class TestNonDictSensitive:
    """AC7: Non-dict sensitive= treated as regular field."""

    def test_non_dict_sensitive_treated_as_regular_field(self) -> None:
        envelope = build_envelope(
            level="INFO",
            message="event",
            extra={"sensitive": "not-a-dict"},
        )
        assert envelope["data"]["sensitive"] == "not-a-dict"

    def test_non_dict_pii_treated_as_regular_field(self) -> None:
        envelope = build_envelope(
            level="INFO",
            message="event",
            extra={"pii": 42},
        )
        assert envelope["data"]["pii"] == 42


class TestEmptySensitive:
    """AC8: Empty sensitive= dict is omitted from envelope."""

    def test_empty_sensitive_dict_omitted(self) -> None:
        envelope = build_envelope(
            level="INFO",
            message="event",
            extra={"sensitive": {}},
        )
        assert "sensitive" not in envelope["data"]

    def test_empty_pii_dict_omitted(self) -> None:
        envelope = build_envelope(
            level="INFO",
            message="event",
            extra={"pii": {}},
        )
        assert "sensitive" not in envelope["data"]
        assert "pii" not in envelope["data"]
