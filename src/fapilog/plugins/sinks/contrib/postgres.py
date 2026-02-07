from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ....core import diagnostics
from ....core.circuit_breaker import SinkCircuitBreaker, SinkCircuitBreakerConfig
from ....core.serialization import SerializedView
from ...utils import parse_plugin_config
from .._batching import BatchingMixin

asyncpg: Any = None  # Lazy import; populated in _ensure_asyncpg

_FIELD_LOCATIONS: dict[str, tuple[str, ...]] = {
    # Root-level fields
    "timestamp": ("timestamp",),
    "level": ("level",),
    "message": ("message",),
    "logger": ("logger",),
    # Context fields
    "message_id": ("context", "message_id"),
    "correlation_id": ("context", "correlation_id"),
    "request_id": ("context", "request_id"),
    "user_id": ("context", "user_id"),
    "tenant_id": ("context", "tenant_id"),
    "trace_id": ("context", "trace_id"),
    "span_id": ("context", "span_id"),
    # Diagnostics fields (exception excluded — nested dict, not a scalar column)
    "origin": ("diagnostics", "origin"),
    "service": ("diagnostics", "service"),
    "env": ("diagnostics", "env"),
    "host": ("diagnostics", "host"),
    "pid": ("diagnostics", "pid"),
}

_FIELD_DEFAULTS: dict[str, Any] = {
    "level": "INFO",
    "logger": "root",
    "message": "",
}

DEFAULT_COLUMN_TYPES: dict[str, str] = {
    "timestamp": "TIMESTAMPTZ",
    "level": "VARCHAR(10)",
    "logger": "VARCHAR(255)",
    "correlation_id": "VARCHAR(64)",
    "message": "TEXT",
}


def _ensure_asyncpg() -> None:
    global asyncpg
    if asyncpg is None:
        import asyncpg as _asyncpg

        asyncpg = _asyncpg


class PostgresSinkConfig(BaseModel):
    """Configuration for PostgreSQL sink."""

    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)

    # Connection settings
    dsn: str | None = Field(default_factory=lambda: os.getenv("FAPILOG_POSTGRES__DSN"))
    host: str = Field(
        default_factory=lambda: os.getenv("FAPILOG_POSTGRES__HOST", "localhost")
    )
    port: int = Field(
        default_factory=lambda: int(os.getenv("FAPILOG_POSTGRES__PORT", "5432"))
    )
    database: str = Field(
        default_factory=lambda: os.getenv("FAPILOG_POSTGRES__DATABASE", "fapilog")
    )
    user: str = Field(
        default_factory=lambda: os.getenv("FAPILOG_POSTGRES__USER", "fapilog")
    )
    password: str | None = Field(
        default_factory=lambda: os.getenv("FAPILOG_POSTGRES__PASSWORD")
    )

    # Table settings
    table_name: str = Field(default="logs")
    schema_name: str = Field(default="public")
    create_table: bool = Field(
        default=True,
        description=(
            "Auto-create table and indexes at startup. WARNING: In production "
            "environments with restricted permissions or change management policies, "
            "set to False and provision tables via migrations. The 'production' preset "
            "sets this to False automatically."
        ),
    )

    # Connection pool settings
    min_pool_size: int = Field(default=2, ge=1)
    max_pool_size: int = Field(default=10, ge=1)
    pool_acquire_timeout: float = Field(default=10.0, gt=0.0)

    # Batching settings
    batch_size: int = Field(default=100, ge=1)
    batch_timeout_seconds: float = Field(default=5.0, gt=0.0)

    # Reliability settings
    max_retries: int = Field(default=3, ge=0)
    retry_base_delay: float = Field(default=0.5, ge=0.0)
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: int = Field(default=5, ge=1)

    # Storage options
    use_jsonb: bool = True
    include_raw_json: bool = True
    extract_fields: list[str] = Field(
        default_factory=lambda: [
            "timestamp",
            "level",
            "logger",
            "correlation_id",
            "message",
        ],
        description=(
            "Fields to extract into dedicated database columns. Supports root-level "
            "fields (timestamp, level, message, logger), context fields (message_id, "
            "correlation_id, request_id, user_id, tenant_id, trace_id, span_id), "
            "and diagnostics fields (origin, service, env, host, pid). Fields are "
            "resolved from their nested location automatically. Unrecognized names "
            "fall back to root-level lookup."
        ),
    )


class PostgresSink(BatchingMixin):
    """PostgreSQL sink with async batching and connection pooling."""

    name = "postgres"

    _logger = logging.getLogger("fapilog.sinks.postgres")

    def __init__(self, config: PostgresSinkConfig | None = None, **kwargs: Any) -> None:
        cfg = parse_plugin_config(PostgresSinkConfig, config, **kwargs)
        self._config = cfg
        # Pool type is Any due to lazy asyncpg import; at runtime it's asyncpg.Pool
        self._pool: Any = None
        self._circuit_breaker: SinkCircuitBreaker | None = None
        self._table_created = False
        self._insert_columns = self._build_insert_columns(cfg.extract_fields)
        self._init_batching(cfg.batch_size, cfg.batch_timeout_seconds)
        self._warn_unrecognized_fields(cfg.extract_fields)

    def _warn_unrecognized_fields(self, fields: list[str]) -> None:
        """Log a warning for any extract_fields not in the known envelope map."""
        known = set(_FIELD_LOCATIONS) | {"event"}
        for field in fields:
            if field not in known:
                self._logger.warning(
                    "extract_fields contains unrecognized field %r; "
                    "it will be looked up at the envelope root and may return NULL "
                    "if the field lives in context or diagnostics",
                    field,
                )

    async def start(self) -> None:
        _ensure_asyncpg()
        pool_kwargs = {
            "min_size": self._config.min_pool_size,
            "max_size": self._config.max_pool_size,
        }

        if self._config.dsn:
            self._pool = await asyncpg.create_pool(dsn=self._config.dsn, **pool_kwargs)
        else:
            self._pool = await asyncpg.create_pool(
                host=self._config.host,
                port=self._config.port,
                database=self._config.database,
                user=self._config.user,
                password=self._config.password,
                **pool_kwargs,
            )

        if self._config.create_table:
            await self._ensure_table()

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
        await self._stop_batching()
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def write(self, entry: dict[str, Any]) -> None:
        await self._enqueue_for_batch(entry)

    async def write_serialized(self, view: SerializedView) -> None:
        """Fast path for pre-serialized payloads."""
        from ....core.errors import SinkWriteError

        try:
            payload = json.loads(bytes(view.data).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            diagnostics.warn(
                "postgres-sink",
                "write_serialized deserialization failed",
                error=str(exc),
                data_size=len(view.data),
                _rate_limit_key="postgres-sink-deserialize",
            )
            raise SinkWriteError(
                f"Failed to deserialize payload in {self.name}.write_serialized",
                sink_name=self.name,
                cause=exc,
            ) from exc

        if not isinstance(payload, dict):
            diagnostics.warn(
                "postgres-sink",
                "write_serialized payload is not a dict",
                payload_type=type(payload).__name__,
                _rate_limit_key="postgres-sink-type",
            )
            raise SinkWriteError(
                f"Payload must be a dict in {self.name}.write_serialized",
                sink_name=self.name,
            )

        await self._enqueue_for_batch(payload)

    async def _send_batch(self, batch: list[dict[str, Any]]) -> None:
        if not batch or self._pool is None:
            return

        if self._circuit_breaker and not self._circuit_breaker.should_allow():
            diagnostics.warn(
                "postgres-sink",
                "circuit breaker open, dropping batch",
                batch_size=len(batch),
                _rate_limit_key="postgres-circuit-open",
            )
            return

        await self._insert_batch_with_retry(batch)

    async def _insert_batch_with_retry(self, batch: list[dict[str, Any]]) -> None:
        attempts = max(1, int(self._config.max_retries))
        for attempt in range(attempts):
            try:
                await self._do_bulk_insert(batch)
                if self._circuit_breaker:
                    self._circuit_breaker.record_success()
                return
            except Exception as exc:
                if self._circuit_breaker:
                    self._circuit_breaker.record_failure()

                diagnostics.warn(
                    "postgres-sink",
                    "batch insert failed",
                    error=str(exc),
                    attempt=attempt + 1,
                    batch_size=len(batch),
                    _rate_limit_key="postgres-insert-error",
                )

                if attempt < attempts - 1:
                    delay = self._config.retry_base_delay * (2**attempt)
                    await asyncio.sleep(delay)

    async def _do_bulk_insert(self, batch: list[dict[str, Any]]) -> None:
        schema = self._quote_ident(self._config.schema_name)
        table = self._quote_ident(self._config.table_name)
        columns = [self._quote_ident(col) for col in self._insert_columns]
        placeholders = ", ".join(f"${i + 1}" for i in range(len(columns)))
        query = f"INSERT INTO {schema}.{table} ({', '.join(columns)}) VALUES ({placeholders})"

        rows = [self._prepare_row(entry) for entry in batch]

        async with self._pool.acquire(
            timeout=self._config.pool_acquire_timeout
        ) as conn:
            await conn.executemany(query, rows)

    def _resolve_field(self, entry: dict[str, Any], field: str) -> Any:
        """Resolve a field name to its value using the v1.1 envelope layout."""
        path = _FIELD_LOCATIONS.get(field)
        if path is not None:
            obj: Any = entry
            for key in path:
                if isinstance(obj, dict):
                    obj = obj.get(key)
                else:
                    return None
            return obj
        # Unknown field — fall back to root lookup
        return entry.get(field)

    def _prepare_row(self, entry: dict[str, Any]) -> tuple[Any, ...]:
        values: list[Any] = []
        event_payload = (
            dict(entry)
            if self._config.include_raw_json
            else {
                k: v
                for k in self._config.extract_fields
                if (v := self._resolve_field(entry, k)) is not None
            }
        )

        for column in self._insert_columns:
            if column == "timestamp":
                values.append(
                    self._parse_timestamp(self._resolve_field(entry, "timestamp"))
                )
            elif column == "event":
                # asyncpg requires JSON string for JSONB columns, not Python dict
                values.append(json.dumps(event_payload, default=str))
            else:
                value = self._resolve_field(entry, column)
                if value is None and column in _FIELD_DEFAULTS:
                    value = _FIELD_DEFAULTS[column]
                values.append(value)

        return tuple(values)

    def _parse_timestamp(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
        if isinstance(value, str):
            try:
                normalized = value.replace("Z", "+00:00")
                parsed = datetime.fromisoformat(normalized)
                if parsed.tzinfo is None:
                    return parsed.replace(tzinfo=timezone.utc)
                return parsed
            except Exception:
                pass
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(float(value), tz=timezone.utc)
            except Exception:
                pass
        return datetime.now(timezone.utc)

    async def _ensure_table(self) -> None:
        if self._table_created or self._pool is None:
            return

        json_type = "JSONB" if self._config.use_jsonb else "JSON"
        schema = self._quote_ident(self._config.schema_name)
        table = self._quote_ident(self._config.table_name)

        column_defs = [
            f"{self._quote_ident(col)} {self._column_type(col, json_type)}"
            for col in self._insert_columns
        ]
        column_defs.insert(0, "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()")
        column_defs.insert(0, "id BIGSERIAL PRIMARY KEY")

        create_schema_sql = (
            f"CREATE SCHEMA IF NOT EXISTS {schema}"
            if self._config.schema_name
            else None
        )
        create_table_sql = (
            f"CREATE TABLE IF NOT EXISTS {schema}.{table} (\n    "
            + ",\n    ".join(column_defs)
            + "\n)"
        )

        index_statements = self._build_index_statements(schema, table)

        async with self._pool.acquire(
            timeout=self._config.pool_acquire_timeout
        ) as conn:
            if create_schema_sql:
                await conn.execute(create_schema_sql)
            await conn.execute(create_table_sql)
            for stmt in index_statements:
                try:
                    await conn.execute(stmt)
                except Exception:
                    # Index creation is best effort
                    diagnostics.warn(
                        "postgres-sink",
                        "index creation failed",
                        statement=stmt,
                        _rate_limit_key="postgres-index",
                    )
        self._table_created = True

    def _build_index_statements(self, schema: str, table: str) -> list[str]:
        stmts: list[str] = []

        if "timestamp" in self._insert_columns:
            stmts.append(
                f"CREATE INDEX IF NOT EXISTS idx_{self._config.table_name}_timestamp "
                f"ON {schema}.{table} (timestamp DESC)"
            )
        if "level" in self._insert_columns:
            stmts.append(
                f"CREATE INDEX IF NOT EXISTS idx_{self._config.table_name}_level "
                f"ON {schema}.{table} (level)"
            )
        if "correlation_id" in self._insert_columns:
            stmts.append(
                f"CREATE INDEX IF NOT EXISTS idx_{self._config.table_name}_correlation_id "
                f"ON {schema}.{table} (correlation_id) WHERE correlation_id IS NOT NULL"
            )
        if self._config.use_jsonb:
            stmts.append(
                f"CREATE INDEX IF NOT EXISTS idx_{self._config.table_name}_event_gin "
                f"ON {schema}.{table} USING GIN (event)"
            )
        return stmts

    def _column_type(self, column: str, json_type: str) -> str:
        if column == "event":
            return f"{json_type} NOT NULL"
        return DEFAULT_COLUMN_TYPES.get(column, "TEXT")

    def _build_insert_columns(self, configured_fields: list[str]) -> list[str]:
        seen: set[str] = set()
        columns: list[str] = []
        for field in configured_fields:
            name = str(field).strip()
            if not name:
                continue
            if name in seen:
                continue
            seen.add(name)
            columns.append(name)

        if "timestamp" not in seen:
            columns.insert(0, "timestamp")
        if "event" not in seen:
            columns.append("event")
        else:
            # Ensure event is last for readability/consistency
            columns = [c for c in columns if c != "event"] + ["event"]
        return columns

    def _quote_ident(self, value: str) -> str:
        escaped = value.replace('"', '""')
        return f'"{escaped}"'

    async def health_check(self) -> bool:
        if not self._pool:
            return False

        if self._circuit_breaker and self._circuit_breaker.is_open:
            return False

        try:
            async with self._pool.acquire(
                timeout=min(5.0, self._config.pool_acquire_timeout)
            ) as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    async def flush(self) -> None:
        """Flush any pending batched events."""
        await self._flush_batch()


PLUGIN_METADATA = {
    "name": "postgres",
    "version": "1.0.0",
    "plugin_type": "sink",
    "entry_point": "fapilog.plugins.sinks.contrib.postgres:PostgresSink",
    "description": "PostgreSQL sink with async batching and connection pooling.",
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "0.3.0"},
    "api_version": "1.0",
    "dependencies": ["asyncpg>=0.28.0"],
}


__all__ = ["PostgresSink", "PostgresSinkConfig", "PLUGIN_METADATA", "SerializedView"]
