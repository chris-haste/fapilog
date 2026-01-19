from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from fapilog import Settings, get_logger
from fapilog.plugins.sinks import fallback as fallback_module
from fapilog.plugins.sinks.fallback import FallbackSink, minimal_redact


class TestFallbackSink:
    def test_name_property(self) -> None:
        class Primary:
            name = "primary"

        fallback = FallbackSink(Primary())

        assert fallback.name == "primary"

    @pytest.mark.asyncio
    async def test_primary_sink_success(self) -> None:
        primary = AsyncMock()
        fallback = FallbackSink(primary)
        entry = {"message": "test"}

        with patch("sys.stderr.write") as stderr_write:
            await fallback.write(entry)

        primary.write.assert_awaited_once_with(entry)
        stderr_write.assert_not_called()

    @pytest.mark.asyncio
    async def test_primary_failure_falls_back_to_stderr(self) -> None:
        primary = AsyncMock()
        primary.write.side_effect = Exception("sink failed")
        fallback = FallbackSink(primary)
        entry = {"message": "test"}

        with patch("sys.stderr.write") as stderr_write:
            await fallback.write(entry)

        stderr_write.assert_called_once()
        written = stderr_write.call_args[0][0]
        assert json.loads(written.strip()) == entry

    @pytest.mark.asyncio
    async def test_fallback_emits_warning(self) -> None:
        primary = AsyncMock()
        primary.write.side_effect = Exception("sink failed")
        primary.name = "primary"
        fallback = FallbackSink(primary)

        with patch("fapilog.plugins.sinks.fallback.diagnostics.warn") as warn_mock:
            with patch("sys.stderr.write"):
                await fallback.write({"message": "test"})

        # Find the fallback-specific warning among all calls
        fallback_calls = [
            c for c in warn_mock.call_args_list if "fallback" in str(c).lower()
        ]
        assert len(fallback_calls) == 1, (
            f"Expected 1 fallback warning, got: {warn_mock.call_args_list}"
        )
        args, kwargs = fallback_calls[0]
        assert args[0] == "sink"
        assert "fallback" in args[1].lower()
        assert kwargs["sink"] == "primary"
        assert kwargs["error"] == "Exception"
        assert kwargs["fallback"] == "stderr"

    @pytest.mark.asyncio
    async def test_stderr_failure_emits_warning_only(self) -> None:
        primary = AsyncMock()
        primary.write.side_effect = Exception("sink failed")
        fallback = FallbackSink(primary)

        with patch("sys.stderr.write", side_effect=Exception("stderr failed")):
            with patch("fapilog.plugins.sinks.fallback.diagnostics.warn") as warn_mock:
                await fallback.write({"message": "test"})

        assert warn_mock.called

    @pytest.mark.asyncio
    async def test_start_stop_delegate(self) -> None:
        primary = AsyncMock()
        primary.start = AsyncMock()
        primary.stop = AsyncMock()
        fallback = FallbackSink(primary)

        await fallback.start()
        await fallback.stop()

        primary.start.assert_awaited_once()
        primary.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_write_serialized_missing(self) -> None:
        class Primary:
            async def write(self, entry: dict) -> None:
                return None

        fallback = FallbackSink(Primary())

        assert await fallback.write_serialized({"data": b"{}"}) is None

    @pytest.mark.asyncio
    async def test_write_serialized_failure_uses_fallback(self) -> None:
        primary = AsyncMock()
        primary.write_serialized.side_effect = RuntimeError("boom")
        fallback = FallbackSink(primary)

        with patch(
            "fapilog.plugins.sinks.fallback.handle_sink_write_failure",
            new=AsyncMock(),
        ) as handler:
            await fallback.write_serialized({"data": b"{}"})

        handler.assert_awaited_once()


class TestFallbackHelpers:
    def test_serialize_entry_unserializable_returns_fallback(self) -> None:
        class BadRepr:
            def __repr__(self) -> str:
                raise RuntimeError("boom")

        entry = {"bad": BadRepr()}
        result = fallback_module._serialize_entry(entry)

        assert result == '{"message":"unserializable"}'

    def test_format_payload_serialized_data_attr(self) -> None:
        class Payload:
            def __init__(self, data: bytes) -> None:
                self.data = data

        payload = Payload(b'{"message":"ok"}')

        assert (
            fallback_module._format_payload(payload, serialized=True)
            == '{"message":"ok"}'
        )

    def test_format_payload_serialized_bytes(self) -> None:
        payload = b'{"message":"ok"}'

        assert (
            fallback_module._format_payload(payload, serialized=True)
            == '{"message":"ok"}'
        )

    def test_format_payload_serialized_decode_error(self) -> None:
        class BadData:
            def decode(self, *_args, **_kwargs) -> str:
                raise UnicodeError("boom")

        class Payload:
            data = BadData()

        result = fallback_module._format_payload(Payload(), serialized=True)

        assert '"message"' in result

    def test_format_payload_serialized_non_data(self) -> None:
        class Payload:
            pass

        result = fallback_module._format_payload(Payload(), serialized=True)

        assert '"message"' in result

    def test_format_payload_non_serialized_non_dict(self) -> None:
        result = fallback_module._format_payload("oops", serialized=False)

        assert '"message"' in result

    def test_handle_sink_write_failure_respects_fallback_flag(self) -> None:
        with patch(
            "fapilog.plugins.sinks.fallback.should_fallback_sink", return_value=False
        ):
            with patch("sys.stderr.write") as stderr_write:
                asyncio.run(
                    fallback_module.handle_sink_write_failure(
                        {"message": "test"},
                        sink=object(),
                        error=RuntimeError("boom"),
                    )
                )

        stderr_write.assert_not_called()

    def test_handle_sink_write_failure_warn_failure_is_contained(self) -> None:
        with patch("sys.stderr.write", side_effect=RuntimeError("stderr failed")):
            with patch(
                "fapilog.plugins.sinks.fallback.diagnostics.warn",
                side_effect=RuntimeError("warn failed"),
            ):
                asyncio.run(
                    fallback_module.handle_sink_write_failure(
                        {"message": "test"},
                        sink=object(),
                        error=RuntimeError("boom"),
                    )
                )


class TestSinkFallbackIntegration:
    def test_fanout_path_falls_back(self) -> None:
        class FailingSink:
            name = "failing"

            async def write(self, entry: dict) -> None:
                raise RuntimeError("boom")

        warn_calls = []
        writes = []

        def _capture_warn(*_args, **kwargs):
            warn_calls.append(kwargs)

        def _capture_write(value: str) -> int:
            writes.append(value)
            return len(value)

        with patch("fapilog.plugins.sinks.fallback.diagnostics.warn", _capture_warn):
            with patch("sys.stderr.write", _capture_write):
                logger = get_logger(sinks=[FailingSink()])
                try:
                    logger.info("fanout failure")
                finally:
                    asyncio.run(logger.stop_and_drain())

        assert writes
        assert warn_calls
        # Filter to sink-related warn calls (other diagnostics may also fire)
        sink_warns = [w for w in warn_calls if "sink" in w]
        assert sink_warns, f"Expected sink warn calls, got: {warn_calls}"
        assert sink_warns[0]["sink"] == "failing"

    def test_routing_path_falls_back(self) -> None:
        class FailingSink:
            name = "failing"

            async def write(self, entry: dict) -> None:
                raise RuntimeError("boom")

        warn_calls = []
        writes = []

        def _capture_warn(*_args, **kwargs):
            warn_calls.append(kwargs)

        def _capture_write(value: str) -> int:
            writes.append(value)
            return len(value)

        settings = Settings(
            sink_routing={
                "enabled": True,
                "rules": [{"levels": ["INFO"], "sinks": ["failing"]}],
            },
        )

        with patch("fapilog.plugins.sinks.fallback.diagnostics.warn", _capture_warn):
            with patch("sys.stderr.write", _capture_write):
                logger = get_logger(settings=settings, sinks=[FailingSink()])
                try:
                    logger.info("routing failure")
                finally:
                    asyncio.run(logger.stop_and_drain())

        assert writes
        assert warn_calls
        # Filter to sink-related warn calls (other diagnostics may also fire)
        sink_warns = [w for w in warn_calls if "sink" in w]
        assert sink_warns, f"Expected sink warn calls, got: {warn_calls}"
        assert sink_warns[0]["sink"] == "failing"

    def test_fanout_handler_failure_is_contained(self) -> None:
        class FailingSink:
            name = "failing"

            async def write(self, entry: dict) -> None:
                raise RuntimeError("boom")

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure",
            side_effect=RuntimeError("handler failure"),
        ) as handler:
            logger = get_logger(sinks=[FailingSink()])
            try:
                logger.info("fanout failure")
            finally:
                asyncio.run(logger.stop_and_drain())

        assert handler.called

    def test_serialized_handler_failure_is_contained(self) -> None:
        class FailingSink:
            name = "failing"

            async def write(self, entry: dict) -> None:
                return None

            async def write_serialized(self, view: object) -> None:
                raise RuntimeError("boom")

        settings = Settings(core={"serialize_in_flush": True})

        with patch(
            "fapilog.core.sink_writers.handle_sink_write_failure",
            side_effect=RuntimeError("handler failure"),
        ) as handler:
            logger = get_logger(settings=settings, sinks=[FailingSink()])
            try:
                logger.info("serialized failure")
            finally:
                asyncio.run(logger.stop_and_drain())

        assert handler.called

    def test_routing_handler_failure_is_contained(self) -> None:
        class FailingSink:
            name = "failing"

            async def write(self, entry: dict) -> None:
                raise RuntimeError("boom")

        settings = Settings(
            sink_routing={
                "enabled": True,
                "rules": [{"levels": ["INFO"], "sinks": ["failing"]}],
            },
        )

        with patch(
            "fapilog.plugins.sinks.fallback.handle_sink_write_failure",
            side_effect=RuntimeError("handler failure"),
        ) as handler:
            logger = get_logger(settings=settings, sinks=[FailingSink()])
            try:
                logger.info("routing failure")
            finally:
                asyncio.run(logger.stop_and_drain())

        assert handler.called


class TestMinimalRedact:
    """Test minimal_redact function (Story 4.46 AC2)."""

    def test_masks_password_field(self) -> None:
        payload = {"user": "alice", "password": "secret123"}
        result = minimal_redact(payload)
        assert result == {"user": "alice", "password": "***"}

    def test_masks_api_key_field(self) -> None:
        payload = {"user": "alice", "api_key": "sk-xxx"}
        result = minimal_redact(payload)
        assert result == {"user": "alice", "api_key": "***"}

    def test_masks_multiple_sensitive_fields(self) -> None:
        payload = {"user": "alice", "password": "secret123", "api_key": "sk-xxx"}
        result = minimal_redact(payload)
        assert result == {"user": "alice", "password": "***", "api_key": "***"}

    def test_case_insensitive_matching(self) -> None:
        payload = {"PASSWORD": "secret", "Api_Key": "sk-xxx", "TOKEN": "tok"}
        result = minimal_redact(payload)
        assert result == {"PASSWORD": "***", "Api_Key": "***", "TOKEN": "***"}

    def test_handles_nested_dicts(self) -> None:
        payload = {
            "user": "alice",
            "login": {"password": "secret", "token": "tok123"},
        }
        result = minimal_redact(payload)
        assert result == {
            "user": "alice",
            "login": {"password": "***", "token": "***"},
        }

    def test_deeply_nested_dicts(self) -> None:
        payload = {"level1": {"level2": {"level3": {"secret": "hidden"}}}}
        result = minimal_redact(payload)
        assert result == {"level1": {"level2": {"level3": {"secret": "***"}}}}

    def test_preserves_non_sensitive_fields(self) -> None:
        payload = {"user": "alice", "email": "alice@example.com", "age": 30}
        result = minimal_redact(payload)
        assert result == {"user": "alice", "email": "alice@example.com", "age": 30}

    def test_handles_empty_dict(self) -> None:
        assert minimal_redact({}) == {}

    def test_handles_non_string_values(self) -> None:
        payload = {"password": 12345, "token": ["a", "b"], "secret": None}
        result = minimal_redact(payload)
        assert result == {"password": "***", "token": "***", "secret": "***"}

    def test_does_not_mutate_original(self) -> None:
        original = {"user": "alice", "password": "secret"}
        minimal_redact(original)
        assert original == {"user": "alice", "password": "secret"}

    def test_handles_list_of_dicts(self) -> None:
        """AC1: List contents are recursively redacted."""
        payload = {"users": [{"password": "secret", "name": "alice"}]}
        result = minimal_redact(payload)
        assert result == {"users": [{"password": "***", "name": "alice"}]}

    def test_handles_nested_lists(self) -> None:
        """AC2: Nested lists containing dicts are redacted."""
        payload = {"matrix": [[{"token": "abc"}], [{"api_key": "xyz"}]]}
        result = minimal_redact(payload)
        assert result == {"matrix": [[{"token": "***"}], [{"api_key": "***"}]]}

    def test_handles_mixed_nesting(self) -> None:
        """AC3: Arbitrary combinations of dicts and lists are handled."""
        payload = {
            "data": {
                "items": [
                    {"login_info": {"password": "secret", "username": "admin"}},
                    {"api_key": "sk-xxx", "public": True},
                ]
            }
        }
        result = minimal_redact(payload)
        assert result["data"]["items"][0]["login_info"]["password"] == "***"
        assert result["data"]["items"][0]["login_info"]["username"] == "admin"
        assert result["data"]["items"][1]["api_key"] == "***"
        assert result["data"]["items"][1]["public"] is True

    def test_preserves_primitive_lists(self) -> None:
        """AC4: Lists containing primitives (strings, numbers) are preserved."""
        payload = {"tags": ["prod", "critical"], "counts": [1, 2, 3]}
        result = minimal_redact(payload)
        assert result == {"tags": ["prod", "critical"], "counts": [1, 2, 3]}

    def test_depth_limit_prevents_overflow(self) -> None:
        """AC5: Extremely deep nesting doesn't cause stack overflow."""
        # Create deeply nested structure (150 levels)
        deep: dict = {"password": "secret"}
        for _ in range(150):
            deep = {"nested": [deep]}

        # Should not raise RecursionError
        result = minimal_redact(deep)

        # Structure should be preserved (redaction may stop at depth limit)
        assert "nested" in result


class TestFallbackRedactionModes:
    """Test fallback redaction modes (Story 4.46 AC1, AC2, AC4)."""

    @pytest.mark.asyncio
    async def test_minimal_mode_redacts_sensitive_fields(self) -> None:
        """AC2: minimal mode applies built-in field masking."""
        primary = AsyncMock()
        primary.write.side_effect = Exception("sink failed")
        fallback = FallbackSink(primary)
        entry = {"user": "alice", "password": "secret123", "api_key": "sk-xxx"}

        with patch("sys.stderr.write") as stderr_write:
            await fallback.write(entry, redact_mode="minimal")

        stderr_write.assert_called_once()
        written = json.loads(stderr_write.call_args[0][0].strip())
        assert written["user"] == "alice"
        assert written["password"] == "***"
        assert written["api_key"] == "***"

    @pytest.mark.asyncio
    async def test_none_mode_no_redaction(self) -> None:
        """AC4: none mode writes unredacted payload."""
        primary = AsyncMock()
        primary.write.side_effect = Exception("sink failed")
        fallback = FallbackSink(primary)
        entry = {"user": "alice", "password": "secret123"}

        with patch("sys.stderr.write") as stderr_write:
            await fallback.write(entry, redact_mode="none")

        stderr_write.assert_called_once()
        written = json.loads(stderr_write.call_args[0][0].strip())
        assert written["password"] == "secret123"

    @pytest.mark.asyncio
    async def test_none_mode_emits_warning(self) -> None:
        """AC1: Warning when fallback triggers without redaction."""
        primary = AsyncMock()
        primary.write.side_effect = Exception("sink failed")
        fallback = FallbackSink(primary)

        with patch("fapilog.plugins.sinks.fallback.diagnostics.warn") as warn_mock:
            with patch("sys.stderr.write"):
                await fallback.write({"message": "test"}, redact_mode="none")

        # Find the unredacted fallback warning
        unredacted_warns = [
            c for c in warn_mock.call_args_list if "without redaction" in str(c)
        ]
        assert len(unredacted_warns) == 1

    @pytest.mark.asyncio
    async def test_default_redact_mode_is_minimal(self) -> None:
        """AC5: Default redact mode should be minimal."""
        primary = AsyncMock()
        primary.write.side_effect = Exception("sink failed")
        fallback = FallbackSink(primary)
        entry = {"user": "alice", "password": "secret123"}

        # Don't pass redact_mode - should default to minimal
        with patch("sys.stderr.write") as stderr_write:
            await fallback.write(entry)

        stderr_write.assert_called_once()
        written = json.loads(stderr_write.call_args[0][0].strip())
        assert written["password"] == "***"

    @pytest.mark.asyncio
    async def test_inherit_mode_no_additional_redaction(self) -> None:
        """AC3: inherit mode uses pipeline redactors (already applied)."""
        primary = AsyncMock()
        primary.write.side_effect = Exception("sink failed")
        fallback = FallbackSink(primary)
        # Simulate entry that was already redacted by pipeline
        entry = {"user": "alice", "password": "already-redacted-by-pipeline"}

        with patch("sys.stderr.write") as stderr_write:
            await fallback.write(entry, redact_mode="inherit")

        stderr_write.assert_called_once()
        written = json.loads(stderr_write.call_args[0][0].strip())
        # "inherit" mode passes through - pipeline already handled redaction
        assert written["password"] == "already-redacted-by-pipeline"

    @pytest.mark.asyncio
    async def test_inherit_mode_no_warning(self) -> None:
        """AC3: inherit mode should NOT emit unredacted fallback warning."""
        primary = AsyncMock()
        primary.write.side_effect = Exception("sink failed")
        fallback = FallbackSink(primary)

        with patch("fapilog.plugins.sinks.fallback.diagnostics.warn") as warn_mock:
            with patch("sys.stderr.write"):
                await fallback.write({"message": "test"}, redact_mode="inherit")

        # Should NOT have unredacted fallback warning (unlike "none" mode)
        unredacted_warns = [
            c for c in warn_mock.call_args_list if "without redaction" in str(c)
        ]
        assert len(unredacted_warns) == 0
