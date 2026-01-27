from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from fapilog import Settings
from fapilog.core.circuit_breaker import CircuitState
from fapilog.plugins import loader
from fapilog.plugins.sinks.contrib import postgres
from fapilog.plugins.sinks.contrib.postgres import PostgresSink, PostgresSinkConfig


class FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self.executemany_calls: list[tuple[str, list[tuple[Any, ...]]]] = []
        self.failures_before_success = 0
        self.raise_execute = False

    async def execute(self, query: str, *args: Any) -> str:
        self.executed.append((query.strip(), tuple(args)))
        if self.raise_execute:
            raise RuntimeError("execute failure")
        return "OK"

    async def executemany(self, query: str, rows: list[tuple[Any, ...]]) -> None:
        self.executemany_calls.append((query.strip(), rows))
        if self.failures_before_success > 0:
            self.failures_before_success -= 1
            raise RuntimeError("bulk insert failure")

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        self.executed.append((query.strip(), tuple(args)))
        return {"ok": True}


class _AcquireCtx:
    def __init__(self, pool: FakePool, kwargs: dict[str, Any]) -> None:
        self._pool = pool
        self._kwargs = kwargs

    async def __aenter__(self) -> FakeConnection:
        self._pool.acquire_calls.append(self._kwargs)
        return self._pool.connection

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None


class FakePool:
    def __init__(self, connection: FakeConnection | None = None) -> None:
        self.connection = connection or FakeConnection()
        self.acquire_calls: list[dict[str, Any]] = []
        self.closed = False
        self.params: dict[str, Any] = {}

    def acquire(self, **kwargs: Any) -> _AcquireCtx:
        return _AcquireCtx(self, kwargs)

    async def close(self) -> None:
        self.closed = True


@pytest.fixture()
def fake_asyncpg(monkeypatch: pytest.MonkeyPatch) -> FakePool:
    pool = FakePool()

    async def create_pool(**kwargs: Any) -> FakePool:
        pool.params = kwargs
        return pool

    monkeypatch.setattr(
        postgres,
        "asyncpg",
        SimpleNamespace(create_pool=create_pool),
    )
    return pool


@pytest.mark.asyncio
async def test_start_creates_pool_and_table(fake_asyncpg: FakePool) -> None:
    sink = PostgresSink(
        PostgresSinkConfig(
            dsn="postgresql://user:pass@localhost/db",
            table_name="unit_logs",
            schema_name="public",
        )
    )
    await sink.start()

    assert fake_asyncpg.params["dsn"] == "postgresql://user:pass@localhost/db"
    assert fake_asyncpg.params["min_size"] == sink._config.min_pool_size  # noqa: SLF001
    assert any("CREATE TABLE" in q for q, _ in fake_asyncpg.connection.executed)
    await sink.stop()
    assert fake_asyncpg.closed is True


@pytest.mark.asyncio
async def test_write_serialized_fast_path(fake_asyncpg: FakePool) -> None:
    sink = PostgresSink(PostgresSinkConfig(batch_size=1, table_name="unit_logs"))
    await sink.start()
    view = postgres.SerializedView(data=b'{"message":"hi","level":"DEBUG"}')
    await sink.write_serialized(view)
    await sink.stop()

    assert fake_asyncpg.connection.executemany_calls
    row = fake_asyncpg.connection.executemany_calls[0][1][0]
    assert "hi" in json.dumps(row[-1])


@pytest.mark.asyncio
async def test_bulk_insert_retries_on_failure(
    fake_asyncpg: FakePool, monkeypatch: pytest.MonkeyPatch
) -> None:
    sleep_calls: list[float] = []
    original_sleep = asyncio.sleep
    monkeypatch.setattr(
        asyncio, "sleep", lambda s: sleep_calls.append(s) or original_sleep(0)
    )

    fake_asyncpg.connection.failures_before_success = 1
    sink = PostgresSink(
        PostgresSinkConfig(batch_size=1, max_retries=2, retry_base_delay=0.01)
    )
    await sink.start()
    await sink.write({"message": "retry-me"})
    await sink.stop()

    assert len(fake_asyncpg.connection.executemany_calls) == 2
    assert sleep_calls, "expected backoff sleep after failure"


@pytest.mark.asyncio
async def test_circuit_breaker_blocks_when_open(
    fake_asyncpg: FakePool,
) -> None:
    sink = PostgresSink(PostgresSinkConfig(batch_size=1))
    await sink.start()
    assert sink._circuit_breaker is not None  # noqa: SLF001
    sink._circuit_breaker._state = CircuitState.OPEN  # type: ignore[attr-defined]  # noqa: SLF001

    await sink.write({"message": "dropped"})
    await sink.stop()

    assert fake_asyncpg.connection.executemany_calls == []


@pytest.mark.asyncio
async def test_health_check_true_and_false_paths(fake_asyncpg: FakePool) -> None:
    sink = PostgresSink(PostgresSinkConfig(batch_size=1))
    await sink.start()

    result = await sink.health_check()
    assert result is True

    sink._pool = None  # noqa: SLF001
    result = await sink.health_check()
    assert result is False

    await sink.stop()


def test_prepare_row_extracts_timestamp_and_message() -> None:
    sink = PostgresSink(PostgresSinkConfig())
    now = "2024-01-15T10:30:00Z"
    row = sink._prepare_row(  # noqa: SLF001
        {
            "timestamp": now,
            "level": "ERROR",
            "logger": "unit",
            "correlation_id": "cid-1",
            "message": "boom",
        }
    )

    assert isinstance(row[0], datetime)
    assert row[0].tzinfo == timezone.utc
    assert row[1] == "ERROR"
    assert row[4] == "boom"


def test_settings_env_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAPILOG_POSTGRES__HOST", "pg-host")
    monkeypatch.setenv("FAPILOG_POSTGRES__PORT", "15432")
    monkeypatch.setenv("FAPILOG_POSTGRES__DATABASE", "pgdb")
    monkeypatch.setenv("FAPILOG_POSTGRES__USER", "pguser")
    monkeypatch.setenv("FAPILOG_POSTGRES__PASSWORD", "pgpass")
    monkeypatch.setenv("FAPILOG_POSTGRES__TABLE_NAME", "pg_logs")
    settings = Settings()

    cfg = settings.sink_config.postgres
    assert cfg.host == "pg-host"
    assert cfg.port == 15432
    assert cfg.database == "pgdb"
    assert cfg.user == "pguser"
    assert cfg.password == "pgpass"
    assert cfg.table_name == "pg_logs"


def test_loader_registers_postgres(fake_asyncpg: FakePool) -> None:
    plugin = loader.load_plugin("fapilog.sinks", "postgres", {})
    assert isinstance(plugin, PostgresSink)


# ---------------------------------------------------------------------------
# Additional test scenarios: Error handling, edge cases, schema variations
# ---------------------------------------------------------------------------


class TestErrorScenarios:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_connection_failure_on_start(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pool creation failure should raise."""

        async def failing_create_pool(**kwargs: Any) -> FakePool:
            raise ConnectionRefusedError("Connection refused")

        monkeypatch.setattr(
            postgres,
            "asyncpg",
            SimpleNamespace(create_pool=failing_create_pool),
        )

        sink = PostgresSink(PostgresSinkConfig(table_name="test"))
        with pytest.raises(ConnectionRefusedError):
            await sink.start()

    @pytest.mark.asyncio
    async def test_pool_exhaustion_timeout(self, fake_asyncpg: FakePool) -> None:
        """Pool acquire timeout should be passed correctly."""
        sink = PostgresSink(
            PostgresSinkConfig(
                batch_size=1, table_name="test", pool_acquire_timeout=2.5
            )
        )
        await sink.start()
        await sink.write({"message": "test"})
        await sink.stop()

        # Verify timeout was passed to acquire calls
        assert any(call.get("timeout") == 2.5 for call in fake_asyncpg.acquire_calls), (
            "pool_acquire_timeout should be passed to acquire()"
        )

    @pytest.mark.asyncio
    async def test_all_retries_exhausted_drops_batch(
        self, fake_asyncpg: FakePool, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When all retries fail, batch is dropped without crashing."""
        original_sleep = asyncio.sleep
        monkeypatch.setattr(asyncio, "sleep", lambda s: original_sleep(0))

        # All attempts will fail
        fake_asyncpg.connection.failures_before_success = 999
        sink = PostgresSink(
            PostgresSinkConfig(batch_size=1, max_retries=3, retry_base_delay=0.001)
        )
        await sink.start()

        # Should not raise
        await sink.write({"message": "will-fail"})
        await sink.stop()

        # Should have attempted max_retries times
        assert len(fake_asyncpg.connection.executemany_calls) == 3

    @pytest.mark.asyncio
    async def test_health_check_returns_false_when_circuit_open(
        self, fake_asyncpg: FakePool
    ) -> None:
        """Health check returns False when circuit breaker is open."""
        sink = PostgresSink(PostgresSinkConfig(batch_size=1))
        await sink.start()

        # Force circuit breaker open
        assert sink._circuit_breaker is not None  # noqa: SLF001
        sink._circuit_breaker._state = CircuitState.OPEN  # type: ignore[attr-defined]  # noqa: SLF001

        result = await sink.health_check()
        assert result is False
        await sink.stop()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_parse_timestamp_with_datetime_object(self) -> None:
        """Datetime objects should be returned with UTC if naive."""
        sink = PostgresSink(PostgresSinkConfig())
        now = datetime.now()
        result = sink._parse_timestamp(now)  # noqa: SLF001
        assert result.tzinfo == timezone.utc

    def test_parse_timestamp_with_aware_datetime(self) -> None:
        """Aware datetime should be returned as-is."""
        sink = PostgresSink(PostgresSinkConfig())
        from datetime import timedelta

        tz = timezone(timedelta(hours=-5))
        aware = datetime(2024, 1, 15, 10, 30, tzinfo=tz)
        result = sink._parse_timestamp(aware)  # noqa: SLF001
        assert result.tzinfo == tz

    def test_parse_timestamp_with_unix_epoch(self) -> None:
        """Unix timestamps (int/float) should be converted."""
        sink = PostgresSink(PostgresSinkConfig())
        ts = 1705315800  # 2024-01-15T10:30:00Z
        result = sink._parse_timestamp(ts)  # noqa: SLF001
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc

    def test_parse_timestamp_with_invalid_value_returns_now(self) -> None:
        """Invalid timestamps should return current time."""
        sink = PostgresSink(PostgresSinkConfig())
        before = datetime.now(timezone.utc)
        result = sink._parse_timestamp("not-a-timestamp")  # noqa: SLF001
        after = datetime.now(timezone.utc)
        assert before <= result <= after

    def test_parse_timestamp_with_none_returns_now(self) -> None:
        """None timestamp should return current time."""
        sink = PostgresSink(PostgresSinkConfig())
        before = datetime.now(timezone.utc)
        result = sink._parse_timestamp(None)  # noqa: SLF001
        after = datetime.now(timezone.utc)
        assert before <= result <= after

    @pytest.mark.asyncio
    async def test_empty_batch_is_noop(self, fake_asyncpg: FakePool) -> None:
        """Empty batch should not trigger any database calls."""
        sink = PostgresSink(PostgresSinkConfig(batch_size=100))
        await sink.start()
        # Call _send_batch directly with empty list
        await sink._send_batch([])  # noqa: SLF001
        await sink.stop()

        # No executemany calls should have been made
        assert fake_asyncpg.connection.executemany_calls == []

    @pytest.mark.asyncio
    async def test_write_serialized_raises_on_invalid_json(
        self, fake_asyncpg: FakePool
    ) -> None:
        """Invalid JSON in write_serialized should raise SinkWriteError (Story 4.53)."""
        from fapilog.core.errors import SinkWriteError

        sink = PostgresSink(PostgresSinkConfig(batch_size=1))
        await sink.start()

        # Invalid JSON - should raise SinkWriteError
        view = postgres.SerializedView(data=b"not valid json {{{")
        with pytest.raises(SinkWriteError) as exc_info:
            await sink.write_serialized(view)
        await sink.stop()

        assert exc_info.value.context.plugin_name == "postgres"
        assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)

    @pytest.mark.asyncio
    async def test_write_serialized_raises_on_non_dict_json(
        self, fake_asyncpg: FakePool
    ) -> None:
        """Non-dict JSON payloads should raise SinkWriteError (Story 4.53)."""
        from fapilog.core.errors import SinkWriteError

        sink = PostgresSink(PostgresSinkConfig(batch_size=1))
        await sink.start()

        # Valid JSON but not a dict - should raise SinkWriteError
        view = postgres.SerializedView(data=b'["array", "not", "dict"]')
        with pytest.raises(SinkWriteError) as exc_info:
            await sink.write_serialized(view)
        await sink.stop()

        assert exc_info.value.context.plugin_name == "postgres"
        # No cause for type mismatch (not a deserialization error)
        assert "dict" in str(exc_info.value).lower()

    def test_prepare_row_with_missing_fields(self) -> None:
        """Missing fields should use defaults."""
        sink = PostgresSink(PostgresSinkConfig())
        row = sink._prepare_row({})  # noqa: SLF001

        # Should have defaults
        assert row[1] == "INFO"  # level default
        assert row[2] == "root"  # logger default
        assert row[4] == ""  # message default


class TestSchemaVariations:
    """Test different schema configurations."""

    def test_custom_extract_fields(self) -> None:
        """Custom extract_fields should build correct column list."""
        sink = PostgresSink(
            PostgresSinkConfig(
                extract_fields=["service", "request_id", "user_id"],
            )
        )
        columns = sink._insert_columns  # noqa: SLF001

        # Should include timestamp (auto-added), custom fields, and event
        assert "timestamp" in columns
        assert "service" in columns
        assert "request_id" in columns
        assert "user_id" in columns
        assert "event" in columns
        # event should be last
        assert columns[-1] == "event"

    def test_extract_fields_deduplication(self) -> None:
        """Duplicate fields should be deduplicated."""
        sink = PostgresSink(
            PostgresSinkConfig(
                extract_fields=["level", "level", "message", "level"],
            )
        )
        columns = sink._insert_columns  # noqa: SLF001

        # Count occurrences of level
        level_count = columns.count("level")
        assert level_count == 1, "level should appear only once"

    def test_extract_fields_with_event_included(self) -> None:
        """Event in extract_fields should be moved to last position."""
        sink = PostgresSink(
            PostgresSinkConfig(
                extract_fields=["event", "level", "message"],
            )
        )
        columns = sink._insert_columns  # noqa: SLF001
        assert columns[-1] == "event"

    @pytest.mark.asyncio
    async def test_json_vs_jsonb_column_type(self, fake_asyncpg: FakePool) -> None:
        """Schema should use JSON or JSONB based on config."""
        # Test JSONB (default)
        sink_jsonb = PostgresSink(
            PostgresSinkConfig(use_jsonb=True, table_name="jsonb_logs")
        )
        await sink_jsonb.start()

        create_stmts = [q for q, _ in fake_asyncpg.connection.executed if "CREATE" in q]
        jsonb_table = [s for s in create_stmts if "jsonb_logs" in s.lower()]
        assert any("JSONB" in s for s in jsonb_table)

        await sink_jsonb.stop()
        fake_asyncpg.connection.executed.clear()

        # Test JSON
        sink_json = PostgresSink(
            PostgresSinkConfig(use_jsonb=False, table_name="json_logs")
        )
        await sink_json.start()

        create_stmts = [q for q, _ in fake_asyncpg.connection.executed if "CREATE" in q]
        json_table = [s for s in create_stmts if "json_logs" in s.lower()]
        # Should have JSON but not JSONB
        has_json_not_jsonb = any("JSON" in s and "JSONB" not in s for s in json_table)
        assert has_json_not_jsonb

        await sink_json.stop()

    @pytest.mark.asyncio
    async def test_create_table_disabled(self, fake_asyncpg: FakePool) -> None:
        """When create_table=False, no schema DDL should run."""
        sink = PostgresSink(
            PostgresSinkConfig(create_table=False, table_name="existing_table")
        )
        await sink.start()

        # No CREATE statements should have been executed
        create_stmts = [q for q, _ in fake_asyncpg.connection.executed if "CREATE" in q]
        assert create_stmts == []

        await sink.stop()

    def test_quote_ident_escapes_special_chars(self) -> None:
        """Identifiers with special characters should be properly escaped."""
        sink = PostgresSink(PostgresSinkConfig())
        assert sink._quote_ident("normal") == '"normal"'  # noqa: SLF001
        assert sink._quote_ident('with"quote') == '"with""quote"'  # noqa: SLF001
        assert sink._quote_ident("with spaces") == '"with spaces"'  # noqa: SLF001


class TestFlushBehavior:
    """Test flush() method behavior."""

    @pytest.mark.asyncio
    async def test_flush_sends_pending_batch(self, fake_asyncpg: FakePool) -> None:
        """flush() should send any pending batched events."""
        sink = PostgresSink(
            PostgresSinkConfig(
                batch_size=100,  # Large batch so it won't auto-flush
                batch_timeout_seconds=60,  # Long timeout
            )
        )
        await sink.start()

        # Write some events (won't auto-flush due to large batch size)
        await sink.write({"message": "event-1"})
        await sink.write({"message": "event-2"})

        # Should not have inserted yet
        assert fake_asyncpg.connection.executemany_calls == []

        # Explicit flush
        await sink.flush()

        # Now should have been inserted
        assert len(fake_asyncpg.connection.executemany_calls) == 1
        rows = fake_asyncpg.connection.executemany_calls[0][1]
        assert len(rows) == 2

        await sink.stop()

    @pytest.mark.asyncio
    async def test_flush_is_noop_when_no_pending(self, fake_asyncpg: FakePool) -> None:
        """flush() with no pending events should be a no-op."""
        sink = PostgresSink(PostgresSinkConfig(batch_size=100))
        await sink.start()

        # Flush with nothing pending
        await sink.flush()

        # No inserts should have happened
        assert fake_asyncpg.connection.executemany_calls == []

        await sink.stop()


class TestDsnVsIndividualParams:
    """Test connection using DSN vs individual parameters."""

    @pytest.mark.asyncio
    async def test_dsn_connection(self, fake_asyncpg: FakePool) -> None:
        """DSN should be passed directly to create_pool."""
        sink = PostgresSink(
            PostgresSinkConfig(
                dsn="postgresql://user:pass@myhost:5433/mydb",
                host="ignored",  # Should be ignored when DSN is set
                port=1234,  # Should be ignored when DSN is set
            )
        )
        await sink.start()

        assert fake_asyncpg.params["dsn"] == "postgresql://user:pass@myhost:5433/mydb"
        # Individual params should not be in pool params
        assert "host" not in fake_asyncpg.params
        assert "port" not in fake_asyncpg.params

        await sink.stop()

    @pytest.mark.asyncio
    async def test_individual_params_connection(self, fake_asyncpg: FakePool) -> None:
        """When no DSN, individual params should be used."""
        sink = PostgresSink(
            PostgresSinkConfig(
                dsn=None,
                host="myhost",
                port=5433,
                database="mydb",
                user="myuser",
                password="mypass",
            )
        )
        await sink.start()

        assert "dsn" not in fake_asyncpg.params
        assert fake_asyncpg.params["host"] == "myhost"
        assert fake_asyncpg.params["port"] == 5433
        assert fake_asyncpg.params["database"] == "mydb"
        assert fake_asyncpg.params["user"] == "myuser"
        assert fake_asyncpg.params["password"] == "mypass"

        await sink.stop()


class TestConcurrentWrites:
    """Test concurrent write behavior."""

    @pytest.mark.asyncio
    async def test_concurrent_writes_to_batch(self, fake_asyncpg: FakePool) -> None:
        """Multiple concurrent writes should be safely batched."""
        sink = PostgresSink(
            PostgresSinkConfig(
                batch_size=10,
                batch_timeout_seconds=0.1,
            )
        )
        await sink.start()

        # Write concurrently
        async def write_events(start: int, count: int) -> None:
            for i in range(count):
                await sink.write({"message": f"event-{start + i}"})

        await asyncio.gather(
            write_events(0, 5),
            write_events(100, 5),
            write_events(200, 5),
        )

        await sink.stop()

        # All 15 events should have been inserted
        total_rows = sum(
            len(rows) for _, rows in fake_asyncpg.connection.executemany_calls
        )
        assert total_rows == 15


class TestIndexCreation:
    """Test index creation behavior."""

    @pytest.mark.asyncio
    async def test_gin_index_only_for_jsonb(self, fake_asyncpg: FakePool) -> None:
        """GIN index should only be created when use_jsonb=True."""
        # With JSONB
        sink_jsonb = PostgresSink(
            PostgresSinkConfig(use_jsonb=True, table_name="test_jsonb")
        )
        await sink_jsonb.start()

        gin_stmts = [q for q, _ in fake_asyncpg.connection.executed if "USING GIN" in q]
        assert len(gin_stmts) > 0, "GIN index should be created for JSONB"

        await sink_jsonb.stop()
        fake_asyncpg.connection.executed.clear()

        # Without JSONB
        sink_json = PostgresSink(
            PostgresSinkConfig(use_jsonb=False, table_name="test_json")
        )
        await sink_json.start()

        gin_stmts = [q for q, _ in fake_asyncpg.connection.executed if "USING GIN" in q]
        assert len(gin_stmts) == 0, "GIN index should not be created for JSON"

        await sink_json.stop()

    @pytest.mark.asyncio
    async def test_index_creation_failure_is_contained(
        self, fake_asyncpg: FakePool
    ) -> None:
        """Index creation failures should be logged but not raise."""
        # Make execute fail for index statements
        original_execute = fake_asyncpg.connection.execute

        async def failing_execute(query: str, *args: Any) -> str:
            if "CREATE INDEX" in query:
                raise RuntimeError("Index creation failed")
            return await original_execute(query, *args)

        fake_asyncpg.connection.execute = failing_execute

        sink = PostgresSink(PostgresSinkConfig(table_name="test_index"))

        # Should not raise despite index failures
        await sink.start()
        await sink.stop()
