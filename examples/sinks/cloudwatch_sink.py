from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

try:  # Optional dependency for environments without AWS SDK installed
    import boto3  # type: ignore
    from botocore.exceptions import ClientError  # type: ignore
except Exception:  # pragma: no cover - import fallback
    boto3 = None

    class ClientError(Exception):
        def __init__(
            self, response: dict[str, Any], operation_name: str | None = None
        ) -> None:
            super().__init__(str(response))
            self.response = response
            self.operation_name = operation_name


@dataclass
class CloudWatchSinkConfig:
    """Configuration for CloudWatch sink."""

    log_group_name: str = field(
        default_factory=lambda: os.getenv(
            "FAPILOG_CLOUDWATCH_LOG_GROUP", "/fapilog/default"
        )
    )
    log_stream_name: str = field(
        default_factory=lambda: os.getenv("FAPILOG_CLOUDWATCH_LOG_STREAM", "default")
    )
    region: str = field(
        default_factory=lambda: os.getenv(
            "AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        )
    )
    batch_size: int = 100
    batch_timeout_seconds: float = 5.0
    create_log_group: bool = True
    create_log_stream: bool = True


class CloudWatchSink:
    """Async sink that batches and sends logs to AWS CloudWatch Logs."""

    name = "cloudwatch"

    def __init__(self, config: CloudWatchSinkConfig | None = None) -> None:
        self._config = config or CloudWatchSinkConfig()
        self._client: Any = None
        self._sequence_token: str | None = None
        self._batch: list[dict[str, Any]] = []
        self._batch_lock = asyncio.Lock()
        self._flush_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if boto3 is None:
            raise ImportError("boto3 is required for CloudWatchSink")

        self._client = await asyncio.to_thread(
            boto3.client,
            "logs",
            region_name=self._config.region,
        )

        if self._config.create_log_group:
            await self._ensure_log_group()
        if self._config.create_log_stream:
            await self._ensure_log_stream()

        self._flush_task = asyncio.create_task(self._flush_loop())

    async def stop(self) -> None:
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self._flush_batch()

    async def write(self, entry: dict) -> None:
        """Add entry to batch for sending."""
        try:
            flush_now = False
            async with self._batch_lock:
                self._batch.append(
                    {
                        "timestamp": int(time.time() * 1000),
                        "message": json.dumps(entry, default=str),
                    }
                )
                if len(self._batch) >= self._config.batch_size:
                    flush_now = True
            if flush_now:
                await self._flush_batch()
        except Exception:
            # Contain errors
            return None

    async def health_check(self) -> bool:
        if not self._client:
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

    async def _ensure_log_group(self) -> None:
        try:
            await asyncio.to_thread(
                self._client.create_log_group,
                logGroupName=self._config.log_group_name,
            )
        except ClientError as e:
            if (
                e.response.get("Error", {}).get("Code")
                != "ResourceAlreadyExistsException"
            ):
                raise

    async def _ensure_log_stream(self) -> None:
        try:
            await asyncio.to_thread(
                self._client.create_log_stream,
                logGroupName=self._config.log_group_name,
                logStreamName=self._config.log_stream_name,
            )
        except ClientError as e:
            if (
                e.response.get("Error", {}).get("Code")
                != "ResourceAlreadyExistsException"
            ):
                raise

    async def _flush_loop(self) -> None:
        while True:
            await asyncio.sleep(self._config.batch_timeout_seconds)
            if self._batch:
                await self._flush_batch()

    async def _flush_batch(self) -> None:
        async with self._batch_lock:
            if not self._batch:
                return
            batch = self._batch[:]
            self._batch = []

        kwargs: dict[str, Any] = {
            "logGroupName": self._config.log_group_name,
            "logStreamName": self._config.log_stream_name,
            "logEvents": sorted(batch, key=lambda x: x["timestamp"]),
        }
        if self._sequence_token:
            kwargs["sequenceToken"] = self._sequence_token

        try:
            response = await asyncio.to_thread(
                self._client.put_log_events,
                **kwargs,
            )
            self._sequence_token = response.get("nextSequenceToken")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in (
                "InvalidSequenceTokenException",
                "DataAlreadyAcceptedException",
            ):
                self._sequence_token = e.response.get("Error", {}).get(
                    "expectedSequenceToken"
                )
                async with self._batch_lock:
                    self._batch = batch + self._batch
            else:
                return None


PLUGIN_METADATA = {
    "name": "cloudwatch",
    "version": "1.0.0",
    "plugin_type": "sink",
    "entry_point": "examples.sinks.cloudwatch_sink:CloudWatchSink",
    "description": "AWS CloudWatch Logs sink with batching.",
    "author": "Fapilog Examples",
    "compatibility": {"min_fapilog_version": "0.4.0"},
    "api_version": "1.0",
    "dependencies": ["boto3>=1.26.0"],
}
