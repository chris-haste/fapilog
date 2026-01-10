from __future__ import annotations

import asyncio
import os
from datetime import datetime

import pytest

pytest.importorskip("asyncpg")
import asyncpg  # noqa: E402

pytestmark = [pytest.mark.integration, pytest.mark.postgres]


def _pg_env(key: str, default: str) -> str:
    return os.getenv(f"FAPILOG_POSTGRES__{key}", default)


def _get_pool_config() -> dict:
    """Return connection config for PostgreSQL pool."""
    return {
        "host": _pg_env("HOST", "localhost"),
        "port": int(_pg_env("PORT", "5432")),
        "database": _pg_env("DATABASE", "fapilog_test"),
        "user": _pg_env("USER", "fapilog"),
        "password": _pg_env("PASSWORD", "fapilog"),
    }


@pytest.fixture()
async def postgres_pool():
    """Create a fresh connection pool for each test to avoid event loop issues."""
    try:
        pool = await asyncpg.create_pool(**_get_pool_config())
    except Exception as exc:
        pytest.skip(f"PostgreSQL not available: {exc}")
    else:
        yield pool
        await pool.close()


@pytest.fixture()
async def clean_table(postgres_pool):
    async with postgres_pool.acquire() as conn:
        await conn.execute("DROP TABLE IF EXISTS public.test_logs")
    yield
    async with postgres_pool.acquire() as conn:
        await conn.execute("DROP TABLE IF EXISTS public.test_logs")


class TestPostgresSinkIntegration:
    @pytest.mark.asyncio
    async def test_creates_table_and_inserts_row(
        self, postgres_pool, clean_table
    ) -> None:
        from fapilog.plugins.sinks.contrib.postgres import (
            PostgresSink,
            PostgresSinkConfig,
        )

        sink = PostgresSink(
            PostgresSinkConfig(
                host=_pg_env("HOST", "localhost"),
                port=int(_pg_env("PORT", "5432")),
                database=_pg_env("DATABASE", "fapilog_test"),
                user=_pg_env("USER", "fapilog"),
                password=_pg_env("PASSWORD", "fapilog"),
                table_name="test_logs",
                batch_size=1,
            )
        )
        await sink.start()
        await sink.write(
            {
                "level": "INFO",
                "message": "hello-postgres",
                "timestamp": "2024-01-15T10:30:00Z",
            }
        )
        await sink.stop()

        async with postgres_pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'test_logs')"
            )
            assert exists
            count = await conn.fetchval("SELECT COUNT(*) FROM public.test_logs")
            assert count == 1

    @pytest.mark.asyncio
    async def test_write_serialized_round_trip(
        self, postgres_pool, clean_table
    ) -> None:
        from fapilog.plugins.sinks.contrib.postgres import (
            PostgresSink,
            PostgresSinkConfig,
            SerializedView,
        )

        sink = PostgresSink(
            PostgresSinkConfig(
                host=_pg_env("HOST", "localhost"),
                port=int(_pg_env("PORT", "5432")),
                database=_pg_env("DATABASE", "fapilog_test"),
                user=_pg_env("USER", "fapilog"),
                password=_pg_env("PASSWORD", "fapilog"),
                table_name="test_logs",
                batch_size=1,
            )
        )
        await sink.start()
        await sink.write_serialized(
            SerializedView(
                data=b'{"level":"ERROR","message":"serialized","correlation_id":"abc-1"}'
            )
        )
        await sink.stop()

        async with postgres_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM public.test_logs LIMIT 1")
            assert row is not None
            assert row["message"] == "serialized"
            assert row["correlation_id"] == "abc-1"

    @pytest.mark.asyncio
    async def test_batch_insert_multiple_rows(self, postgres_pool, clean_table) -> None:
        from fapilog.plugins.sinks.contrib.postgres import (
            PostgresSink,
            PostgresSinkConfig,
        )

        sink = PostgresSink(
            PostgresSinkConfig(
                host=_pg_env("HOST", "localhost"),
                port=int(_pg_env("PORT", "5432")),
                database=_pg_env("DATABASE", "fapilog_test"),
                user=_pg_env("USER", "fapilog"),
                password=_pg_env("PASSWORD", "fapilog"),
                table_name="test_logs",
                batch_size=50,
                batch_timeout_seconds=0.1,
            )
        )
        await sink.start()
        for i in range(75):
            await sink.write(
                {
                    "level": "INFO",
                    "message": f"row-{i}",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        await asyncio.sleep(0.2)
        await sink.stop()

        async with postgres_pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM public.test_logs")
            assert count == 75
