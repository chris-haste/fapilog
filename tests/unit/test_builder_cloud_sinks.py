"""Unit tests for cloud sink builder methods (Story 10.24)."""

from __future__ import annotations

from fapilog.builder import LoggerBuilder


class TestAddCloudWatch:
    """Tests for add_cloudwatch() builder method."""

    def test_add_cloudwatch_basic_adds_sink(self) -> None:
        """Verify add_cloudwatch() adds cloudwatch sink with required params."""
        builder = LoggerBuilder()
        builder.add_cloudwatch(log_group="/myapp/prod")

        assert len(builder._sinks) == 1
        assert builder._sinks[0]["name"] == "cloudwatch"
        assert builder._sinks[0]["config"]["log_group_name"] == "/myapp/prod"

    def test_add_cloudwatch_returns_builder_for_chaining(self) -> None:
        """Verify add_cloudwatch() returns builder instance."""
        builder = LoggerBuilder()
        result = builder.add_cloudwatch(log_group="/myapp/prod")

        assert result is builder

    def test_add_cloudwatch_all_options(self) -> None:
        """Verify add_cloudwatch() maps all optional parameters."""
        builder = LoggerBuilder()
        builder.add_cloudwatch(
            log_group="/myapp/prod",
            stream="web-server-1",
            region="us-east-1",
            endpoint_url="http://localhost:4566",
            batch_size=100,
            batch_timeout="5s",
            max_retries=3,
            retry_delay=0.5,
            create_group=True,
            create_stream=True,
            circuit_breaker=True,
            circuit_breaker_threshold=5,
        )

        config = builder._sinks[0]["config"]
        assert config["log_group_name"] == "/myapp/prod"
        assert config["log_stream_name"] == "web-server-1"
        assert config["region"] == "us-east-1"
        assert config["endpoint_url"] == "http://localhost:4566"
        assert config["batch_size"] == 100
        assert config["batch_timeout_seconds"] == 5.0
        assert config["max_retries"] == 3
        assert config["retry_base_delay"] == 0.5
        assert config["create_log_group"] is True
        assert config["create_log_stream"] is True
        assert config["circuit_breaker_enabled"] is True
        assert config["circuit_breaker_threshold"] == 5

    def test_add_cloudwatch_duration_accepts_float(self) -> None:
        """Verify duration params accept float seconds."""
        builder = LoggerBuilder()
        builder.add_cloudwatch(
            log_group="/myapp/prod",
            batch_timeout=10.0,
            retry_delay=1.5,
        )

        config = builder._sinks[0]["config"]
        assert config["batch_timeout_seconds"] == 10.0
        assert config["retry_base_delay"] == 1.5

    def test_add_cloudwatch_optional_params_not_set_when_none(self) -> None:
        """Verify optional params are not included when None."""
        builder = LoggerBuilder()
        builder.add_cloudwatch(log_group="/myapp/prod")

        config = builder._sinks[0]["config"]
        assert "log_stream_name" not in config
        assert "region" not in config
        assert "endpoint_url" not in config


class TestAddLoki:
    """Tests for add_loki() builder method."""

    def test_add_loki_basic_adds_sink(self) -> None:
        """Verify add_loki() adds loki sink with defaults."""
        builder = LoggerBuilder()
        builder.add_loki()

        assert len(builder._sinks) == 1
        assert builder._sinks[0]["name"] == "loki"
        assert builder._sinks[0]["config"]["url"] == "http://localhost:3100"

    def test_add_loki_returns_builder_for_chaining(self) -> None:
        """Verify add_loki() returns builder instance."""
        builder = LoggerBuilder()
        result = builder.add_loki("http://loki:3100")

        assert result is builder

    def test_add_loki_all_options(self) -> None:
        """Verify add_loki() maps all optional parameters."""
        builder = LoggerBuilder()
        builder.add_loki(
            url="http://loki:3100",
            tenant_id="myapp",
            labels={"service": "api", "env": "prod"},
            label_keys=["level", "logger"],
            batch_size=100,
            batch_timeout="5s",
            timeout="10s",
            max_retries=3,
            retry_delay=0.5,
            auth_username="user",
            auth_password="pass",
            auth_token="secret",
            circuit_breaker=True,
            circuit_breaker_threshold=5,
        )

        config = builder._sinks[0]["config"]
        assert config["url"] == "http://loki:3100"
        assert config["tenant_id"] == "myapp"
        assert config["labels"] == {"service": "api", "env": "prod"}
        assert config["label_keys"] == ["level", "logger"]
        assert config["batch_size"] == 100
        assert config["batch_timeout_seconds"] == 5.0
        assert config["timeout_seconds"] == 10.0
        assert config["max_retries"] == 3
        assert config["retry_base_delay"] == 0.5
        assert config["auth_username"] == "user"
        assert config["auth_password"] == "pass"
        assert config["auth_token"] == "secret"
        assert config["circuit_breaker_enabled"] is True
        assert config["circuit_breaker_threshold"] == 5

    def test_add_loki_with_auth_token_only(self) -> None:
        """Verify add_loki() works with just auth_token."""
        builder = LoggerBuilder()
        builder.add_loki(url="http://loki:3100", auth_token="bearer-token")

        config = builder._sinks[0]["config"]
        assert config["auth_token"] == "bearer-token"
        assert "auth_username" not in config
        assert "auth_password" not in config

    def test_add_loki_optional_params_not_set_when_none(self) -> None:
        """Verify optional params are not included when None."""
        builder = LoggerBuilder()
        builder.add_loki()

        config = builder._sinks[0]["config"]
        assert "tenant_id" not in config
        assert "labels" not in config
        assert "label_keys" not in config
        assert "auth_username" not in config
        assert "auth_password" not in config
        assert "auth_token" not in config


class TestAddPostgres:
    """Tests for add_postgres() builder method."""

    def test_add_postgres_with_dsn_adds_sink(self) -> None:
        """Verify add_postgres() with DSN adds postgres sink."""
        builder = LoggerBuilder()
        builder.add_postgres(dsn="postgresql://user:pass@host/db")

        assert len(builder._sinks) == 1
        assert builder._sinks[0]["name"] == "postgres"
        assert builder._sinks[0]["config"]["dsn"] == "postgresql://user:pass@host/db"

    def test_add_postgres_returns_builder_for_chaining(self) -> None:
        """Verify add_postgres() returns builder instance."""
        builder = LoggerBuilder()
        result = builder.add_postgres(host="db.example.com", database="logs")

        assert result is builder

    def test_add_postgres_with_params_adds_sink(self) -> None:
        """Verify add_postgres() with individual params works."""
        builder = LoggerBuilder()
        builder.add_postgres(
            host="db.example.com",
            port=5432,
            database="logs",
            user="logger",
            password="secret",
            table="app_logs",
        )

        config = builder._sinks[0]["config"]
        assert config["host"] == "db.example.com"
        assert config["port"] == 5432
        assert config["database"] == "logs"
        assert config["user"] == "logger"
        assert config["password"] == "secret"
        assert config["table_name"] == "app_logs"

    def test_add_postgres_all_options(self) -> None:
        """Verify add_postgres() maps all optional parameters."""
        builder = LoggerBuilder()
        builder.add_postgres(
            dsn="postgresql://user:pass@host/db",
            host="localhost",
            port=5432,
            database="fapilog",
            user="fapilog",
            password="secret",
            table="logs",
            schema="public",
            batch_size=100,
            batch_timeout="5s",
            max_retries=3,
            retry_delay=0.5,
            min_pool=2,
            max_pool=10,
            pool_acquire_timeout="10s",
            create_table=True,
            use_jsonb=True,
            include_raw_json=True,
            extract_fields=["timestamp", "level", "message"],
            circuit_breaker=True,
            circuit_breaker_threshold=5,
        )

        config = builder._sinks[0]["config"]
        assert config["dsn"] == "postgresql://user:pass@host/db"
        assert config["host"] == "localhost"
        assert config["port"] == 5432
        assert config["database"] == "fapilog"
        assert config["user"] == "fapilog"
        assert config["password"] == "secret"
        assert config["table_name"] == "logs"
        assert config["schema_name"] == "public"
        assert config["batch_size"] == 100
        assert config["batch_timeout_seconds"] == 5.0
        assert config["max_retries"] == 3
        assert config["retry_base_delay"] == 0.5
        assert config["min_pool_size"] == 2
        assert config["max_pool_size"] == 10
        assert config["pool_acquire_timeout"] == 10.0
        assert config["create_table"] is True
        assert config["use_jsonb"] is True
        assert config["include_raw_json"] is True
        assert config["extract_fields"] == ["timestamp", "level", "message"]
        assert config["circuit_breaker_enabled"] is True
        assert config["circuit_breaker_threshold"] == 5

    def test_add_postgres_optional_params_not_set_when_none(self) -> None:
        """Verify optional params are not included when None."""
        builder = LoggerBuilder()
        builder.add_postgres(host="localhost", database="logs")

        config = builder._sinks[0]["config"]
        assert "dsn" not in config
        assert "password" not in config
        assert "extract_fields" not in config


class TestMultipleCloudSinks:
    """Tests for chaining multiple cloud sinks."""

    def test_multiple_cloud_sinks_chainable(self) -> None:
        """Verify users can add multiple cloud sinks in one builder chain."""
        builder = LoggerBuilder()
        result = (
            builder.add_cloudwatch(log_group="/myapp/prod", region="us-east-1")
            .add_loki(url="http://loki:3100")
            .add_file("logs/backup")
        )

        assert result is builder
        assert len(builder._sinks) == 3
        assert builder._sinks[0]["name"] == "cloudwatch"
        assert builder._sinks[1]["name"] == "loki"
        assert builder._sinks[2]["name"] == "rotating_file"

    def test_all_three_cloud_sinks_chainable(self) -> None:
        """Verify all three cloud sinks can be chained."""
        builder = LoggerBuilder()
        builder.add_cloudwatch(log_group="/logs").add_loki().add_postgres(
            dsn="postgresql://user:pass@host/db"
        )

        assert len(builder._sinks) == 3
        sink_names = [s["name"] for s in builder._sinks]
        assert sink_names == ["cloudwatch", "loki", "postgres"]

    def test_cloud_sinks_with_circuit_breaker_config(self) -> None:
        """Verify cloud sinks support per-sink circuit breaker config."""
        builder = LoggerBuilder()
        builder.add_cloudwatch(
            log_group="/myapp/prod",
            circuit_breaker=True,
            circuit_breaker_threshold=3,
        )

        config = builder._sinks[0]["config"]
        assert config["circuit_breaker_enabled"] is True
        assert config["circuit_breaker_threshold"] == 3
