"""Tests for data kwarg flattening in envelope building (Story 10.40)."""

from __future__ import annotations

from fapilog.core.envelope import build_envelope


class TestDataDictFlattening:
    """Test that data={...} kwarg is flattened into envelope data section."""

    def test_data_dict_flattened_into_envelope_data(self) -> None:
        """AC1: data={...} contents are merged into envelope's data section."""
        envelope = build_envelope(
            level="INFO",
            message="test",
            extra={"data": {"username": "alice", "password": "secret"}},
        )

        # Contents should be flattened, not nested
        assert envelope["data"] == {"username": "alice", "password": "secret"}

    def test_explicit_kwargs_override_data_dict_values(self) -> None:
        """AC2: Explicit kwargs win over data dict values on collision."""
        envelope = build_envelope(
            level="INFO",
            message="test",
            extra={
                "data": {"source": "from_dict", "other": "value"},
                "source": "explicit_kwarg",
            },
        )

        assert envelope["data"]["source"] == "explicit_kwarg"  # Explicit wins
        assert envelope["data"]["other"] == "value"  # From data dict

    def test_non_dict_data_preserved_as_nested(self) -> None:
        """AC4: Non-dict data values are stored nested under 'data' key."""
        envelope = build_envelope(
            level="INFO",
            message="test",
            extra={"data": "just a string"},
        )

        assert envelope["data"] == {"data": "just a string"}

    def test_non_dict_data_list_preserved_as_nested(self) -> None:
        """AC4: List data values are stored nested under 'data' key."""
        envelope = build_envelope(
            level="INFO",
            message="test",
            extra={"data": [1, 2, 3]},
        )

        assert envelope["data"] == {"data": [1, 2, 3]}

    def test_empty_data_dict_handled(self) -> None:
        """Empty data dict should not cause errors and results in empty data."""
        envelope = build_envelope(
            level="INFO",
            message="test",
            extra={"data": {}},
        )

        assert envelope["data"] == {}

    def test_data_dict_with_context_fields_routes_to_context(self) -> None:
        """Context fields in data dict should be routed to context, not data."""
        envelope = build_envelope(
            level="INFO",
            message="test",
            extra={"data": {"request_id": "req-123", "username": "alice"}},
        )

        # request_id should go to context
        assert envelope["context"]["request_id"] == "req-123"
        # username should go to data
        assert envelope["data"] == {"username": "alice"}

    def test_data_dict_combined_with_bound_context(self) -> None:
        """data dict should work alongside bound_context."""
        envelope = build_envelope(
            level="INFO",
            message="test",
            bound_context={"service": "auth"},
            extra={"data": {"action": "login"}},
        )

        assert envelope["data"]["service"] == "auth"  # From bound_context
        assert envelope["data"]["action"] == "login"  # From data dict

    def test_explicit_kwarg_overrides_data_dict_and_bound_context(self) -> None:
        """Explicit extra kwarg wins over both data dict and bound_context."""
        envelope = build_envelope(
            level="INFO",
            message="test",
            bound_context={"key": "from_bound"},
            extra={
                "data": {"key": "from_data_dict"},
                "key": "from_explicit",
            },
        )

        # Explicit kwarg should win
        assert envelope["data"]["key"] == "from_explicit"

    def test_data_dict_values_override_bound_context(self) -> None:
        """Data dict values should override bound_context for same keys."""
        envelope = build_envelope(
            level="INFO",
            message="test",
            bound_context={"key": "from_bound"},
            extra={"data": {"key": "from_data_dict"}},
        )

        # Data dict should win over bound_context
        assert envelope["data"]["key"] == "from_data_dict"


class TestContractEnvelopeToSerialization:
    """Contract test: envelopes with flattened data serialize correctly."""

    def test_flattened_envelope_serializes_correctly(self) -> None:
        """AC5: Flattened envelopes pass through serialization pipeline."""
        from fapilog.core.serialization import serialize_envelope

        envelope = build_envelope(
            level="INFO",
            message="test",
            extra={"data": {"key": "value"}, "other": "field"},
        )

        # Must not raise - serialization accepts flattened envelope
        serialized = serialize_envelope(envelope)
        assert b'"key"' in serialized.data
        assert b'"value"' in serialized.data
