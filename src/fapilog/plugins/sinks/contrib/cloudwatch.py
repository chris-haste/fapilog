"""AWS CloudWatch Logs sink with batching, retry, and circuit breaker.

This sink demonstrates the SDK-based integration pattern:
- Wraps blocking boto3 calls in asyncio.to_thread()
- Handles AWS-specific authentication via environment/IAM
- Manages cloud resources (creates log group/stream if needed)
- Handles provider-specific quirks (sequence tokens)

Use this as a reference for building sinks for other SDK-based
providers (GCP, Azure SDK, Kafka, etc.).
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ....core import diagnostics
from ....core.circuit_breaker import SinkCircuitBreaker, SinkCircuitBreakerConfig
from ....core.serialization import SerializedView
from ...utils import parse_plugin_config
from .._batching import BatchingMixin

try:  # Optional dependency
    import boto3
    from botocore.exceptions import ClientError
except Exception:  # pragma: no cover - optional import fallback
    boto3 = None

    class ClientError(Exception):  # type: ignore[no-redef]
        """Fallback ClientError when boto3 is not installed."""

        def __init__(
            self, response: dict[str, Any], operation_name: str | None = None
        ) -> None:
            super().__init__(str(response))
            self.response = response
            self.operation_name = operation_name


# CloudWatch historically had a 256 KB per-event limit. AWS increased this to
# 1 MB in late 2024, but we keep the conservative limit for broad compatibility.
# Users needing larger events can implement a custom sink with higher limits.
MAX_EVENT_SIZE_BYTES = 256 * 1024  # 256 KB (conservative)
MAX_BATCH_SIZE = 10_000
MAX_BATCH_BYTES = 1_048_576  # 1 MB


class CloudWatchSinkConfig(BaseModel):
    """Configuration for AWS CloudWatch Logs sink."""

    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)

    log_group_name: str = "/fapilog/default"
    log_stream_name: str | None = None
    region: str | None = Field(
        default_factory=lambda: os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION"))
    )
    create_log_group: bool = True
    create_log_stream: bool = True
    batch_size: int = Field(default=100, ge=1)
    batch_timeout_seconds: float = Field(default=5.0, gt=0.0)
    max_retries: int = Field(default=3, ge=0)
    retry_base_delay: float = Field(default=0.5, ge=0.0)
    endpoint_url: str | None = None  # For LocalStack/testing
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: int = Field(default=5, ge=1)


class CloudWatchSink(BatchingMixin):
    """AWS CloudWatch Logs sink with batching, retry, and circuit breaker.

    This sink demonstrates the SDK-based integration pattern:
    - Wraps blocking boto3 calls in asyncio.to_thread()
    - Handles AWS-specific authentication via environment/IAM
    - Manages cloud resources (creates log group/stream if needed)
    - Handles provider-specific quirks (sequence tokens)

    Use this as a reference for building sinks for other SDK-based
    providers (GCP, Azure SDK, Kafka, etc.).
    """

    name = "cloudwatch"

    def __init__(
        self, config: CloudWatchSinkConfig | None = None, **kwargs: Any
    ) -> None:
        cfg = parse_plugin_config(CloudWatchSinkConfig, config, **kwargs)
        self._config = cfg
        self._log_stream_name: str | None = cfg.log_stream_name  # Mutable copy
        self._client: Any = None
        self._sequence_token: str | None = None
        self._circuit_breaker: SinkCircuitBreaker | None = None
        self._init_batching(cfg.batch_size, cfg.batch_timeout_seconds)

    async def start(self) -> None:
        """Initialize boto3 client and ensure log group/stream exist."""
        if boto3 is None:
            raise ImportError("boto3 is required for CloudWatchSink")

        client_kwargs: dict[str, Any] = {}
        if self._config.region:
            client_kwargs["region_name"] = self._config.region
        if self._config.endpoint_url:
            client_kwargs["endpoint_url"] = self._config.endpoint_url

        self._client = await asyncio.to_thread(boto3.client, "logs", **client_kwargs)

        if self._config.create_log_group:
            await self._ensure_log_group()
        if self._config.create_log_stream:
            await self._ensure_log_stream()

        if self._config.circuit_breaker_enabled:
            self._circuit_breaker = SinkCircuitBreaker(
                self.name,
                SinkCircuitBreakerConfig(
                    enabled=True,
                    failure_threshold=self._config.circuit_breaker_threshold,
                ),
            )

        await self._start_batching()

    async def stop(self) -> None:
        """Flush pending batches and release client."""
        await self._stop_batching()
        self._client = None

    async def write(self, entry: dict[str, Any]) -> None:
        """Write a single log entry, formatting and enqueueing for batch."""
        event = self._format_event(entry)
        if event is not None:
            await self._enqueue_for_batch(event)

    async def write_serialized(self, view: SerializedView) -> None:
        """Fast path for pre-serialized payloads."""
        from ....core.errors import SinkWriteError

        try:
            message = bytes(view.data).decode("utf-8")
        except UnicodeDecodeError as exc:
            diagnostics.warn(
                "cloudwatch-sink",
                "write_serialized deserialization failed",
                error=str(exc),
                data_size=len(view.data),
                _rate_limit_key="cloudwatch-sink-deserialize",
            )
            raise SinkWriteError(
                f"Failed to deserialize payload in {self.name}.write_serialized",
                sink_name=self.name,
                cause=exc,
            ) from exc
        if len(message.encode("utf-8")) > MAX_EVENT_SIZE_BYTES:
            self._emit_dropped(message_size=len(message.encode("utf-8")))
            return
        event = {"timestamp": int(time.time() * 1000), "message": message}
        await self._enqueue_for_batch(event)

    async def _send_batch(self, batch: list[dict[str, Any]]) -> None:
        """Send a batch of events to CloudWatch, chunking as needed."""
        if not batch:
            return
        if self._circuit_breaker and not self._circuit_breaker.should_allow():
            diagnostics.warn(
                "sink",
                "cloudwatch circuit open, dropping batch",
                batch_size=len(batch),
                _rate_limit_key="cloudwatch-open",
            )
            return

        log_events: list[dict[str, Any]] = []
        for item in batch:
            if "timestamp" in item and "message" in item:
                log_events.append(item)
            else:
                event = self._format_event(item)
                if event is not None:
                    log_events.append(event)

        if not log_events:
            return

        log_events.sort(key=lambda x: x["timestamp"])

        for chunk in self._chunk_events(log_events):
            await self._put_log_events_with_retry(chunk)

    def _chunk_events(self, events: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        """Split events into chunks respecting CloudWatch limits.

        CloudWatch enforces:
        - Max 10,000 events per PutLogEvents call
        - Max 1 MB total payload per call
        - Max 256 KB per individual event (filtered earlier)

        Args:
            events: List of formatted log events with timestamp and message.

        Returns:
            List of event chunks, each within CloudWatch limits.
        """
        chunks: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []
        current_bytes = 0

        for event in events:
            message_bytes = len(event["message"].encode("utf-8"))
            if message_bytes > MAX_EVENT_SIZE_BYTES:
                self._emit_dropped(message_size=message_bytes)
                continue

            if (
                len(current) >= MAX_BATCH_SIZE
                or current_bytes + message_bytes > MAX_BATCH_BYTES
            ):
                if current:
                    chunks.append(current)
                current = []
                current_bytes = 0

            current.append(event)
            current_bytes += message_bytes

        if current:
            chunks.append(current)
        return chunks

    async def _put_log_events_with_retry(
        self, log_events: list[dict[str, Any]]
    ) -> None:
        """Send log events with retry and sequence token handling."""
        if not log_events or self._client is None:
            return
        attempts = max(1, int(self._config.max_retries))
        for attempt in range(attempts):
            try:
                kwargs: dict[str, Any] = {
                    "logGroupName": self._config.log_group_name,
                    "logStreamName": self._log_stream_name,
                    "logEvents": log_events,
                }
                if self._sequence_token:
                    kwargs["sequenceToken"] = self._sequence_token
                response = await asyncio.to_thread(
                    self._client.put_log_events, **kwargs
                )
                self._sequence_token = response.get("nextSequenceToken")
                if self._circuit_breaker:
                    self._circuit_breaker.record_success()
                return
            except ClientError as e:
                code = e.response.get("Error", {}).get("Code", "")

                # Sequence token errors are recoverable - don't count as circuit failure
                if code in (
                    "InvalidSequenceTokenException",
                    "DataAlreadyAcceptedException",
                ):
                    self._sequence_token = e.response.get("Error", {}).get(
                        "expectedSequenceToken"
                    )
                    # Retry immediately with corrected token (no failure recorded)
                    continue

                if code == "ResourceNotFoundException":
                    diagnostics.warn(
                        "sink",
                        "cloudwatch resource missing",
                        error_code=code,
                        _rate_limit_key="cloudwatch-resource",
                    )
                    if self._config.create_log_group:
                        await self._ensure_log_group()
                    if self._config.create_log_stream:
                        await self._ensure_log_stream()
                    if self._circuit_breaker:
                        self._circuit_breaker.record_failure()
                    continue

                if code == "ThrottlingException":
                    if self._circuit_breaker:
                        self._circuit_breaker.record_failure()
                    delay = self._config.retry_base_delay * (2**attempt)
                    await asyncio.sleep(delay)
                    continue

                # Other errors are true failures
                if self._circuit_breaker:
                    self._circuit_breaker.record_failure()
                diagnostics.warn(
                    "sink",
                    "cloudwatch send failed",
                    error_code=code,
                    attempt=attempt + 1,
                    batch_size=len(log_events),
                    _rate_limit_key="cloudwatch-error",
                )
            except Exception as exc:
                if self._circuit_breaker:
                    self._circuit_breaker.record_failure()
                diagnostics.warn(
                    "sink",
                    "cloudwatch unknown error",
                    error=str(exc),
                    _rate_limit_key="cloudwatch-error",
                )
            delay = self._config.retry_base_delay * (2**attempt)
            await asyncio.sleep(delay)

    async def _ensure_log_group(self) -> None:
        """Create log group if it doesn't exist (idempotent)."""
        if self._client is None:
            return
        try:
            await asyncio.to_thread(
                self._client.create_log_group,
                logGroupName=self._config.log_group_name,
            )
            diagnostics.debug(
                "sink",
                "cloudwatch log group created",
                log_group=self._config.log_group_name,
            )
        except ClientError as e:
            if (
                e.response.get("Error", {}).get("Code")
                != "ResourceAlreadyExistsException"
            ):
                raise

    async def _ensure_log_stream(self) -> None:
        """Create log stream if it doesn't exist (idempotent)."""
        if self._client is None:
            return
        if not self._log_stream_name:
            hostname = socket.gethostname()
            self._log_stream_name = f"{hostname}-{int(time.time())}"
        try:
            await asyncio.to_thread(
                self._client.create_log_stream,
                logGroupName=self._config.log_group_name,
                logStreamName=self._log_stream_name,
            )
            diagnostics.debug(
                "sink",
                "cloudwatch log stream created",
                log_group=self._config.log_group_name,
                log_stream=self._log_stream_name,
            )
        except ClientError as e:
            if (
                e.response.get("Error", {}).get("Code")
                != "ResourceAlreadyExistsException"
            ):
                raise

    async def health_check(self) -> bool:
        """Return True if the sink can communicate with CloudWatch."""
        if self._client is None:
            return False
        if self._circuit_breaker and self._circuit_breaker.is_open:
            return False
        try:
            await asyncio.to_thread(
                self._client.describe_log_streams,
                logGroupName=self._config.log_group_name,
                limit=1,
            )
            return True
        except Exception:
            return False

    def _format_event(self, entry: dict[str, Any]) -> dict[str, Any] | None:
        """Format a log entry as a CloudWatch log event.

        Args:
            entry: Raw log entry dictionary.

        Returns:
            CloudWatch event dict with timestamp and message, or None if
            the entry cannot be serialized or exceeds size limits.
        """
        try:
            message = json.dumps(entry, default=str)
        except Exception:
            return None

        size_bytes = len(message.encode("utf-8"))
        if size_bytes > MAX_EVENT_SIZE_BYTES:
            self._emit_dropped(message_size=size_bytes)
            return None

        return {"timestamp": int(time.time() * 1000), "message": message}

    def _emit_dropped(self, *, message_size: int) -> None:
        """Emit a diagnostic warning when an event is dropped due to size.

        Args:
            message_size: Size of the dropped message in bytes.
        """
        try:
            diagnostics.warn(
                "sink",
                "cloudwatch event dropped",
                reason="max_event_size_exceeded",
                size=message_size,
                limit=MAX_EVENT_SIZE_BYTES,
                _rate_limit_key="cloudwatch-size",
            )
        except Exception:
            return


# Plugin metadata for discovery and compatibility checking.
# Note: entry_point is a Python module path for internal registration,
# not a setuptools entry-point. The sink is registered via register_builtin()
# in fapilog.plugins.sinks.__init__.
PLUGIN_METADATA = {
    "name": "cloudwatch",
    "version": "1.0.0",
    "plugin_type": "sink",
    "entry_point": "fapilog.plugins.sinks.contrib.cloudwatch:CloudWatchSink",
    "description": "AWS CloudWatch Logs sink with batching, retry, and circuit breaker.",
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "0.3.0"},
    "api_version": "1.0",
    "dependencies": ["boto3>=1.26.0"],
}
