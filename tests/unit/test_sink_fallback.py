from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from fapilog import Settings, get_logger
from fapilog.plugins.sinks import fallback as fallback_module
from fapilog.plugins.sinks.fallback import FallbackSink


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

        warn_mock.assert_called_once()
        args, kwargs = warn_mock.call_args
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
        assert warn_calls[0]["sink"] == "failing"

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
        assert warn_calls[0]["sink"] == "failing"

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
