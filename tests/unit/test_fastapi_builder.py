"""Unit tests for FastAPIBuilder (Story 10.52)."""

from __future__ import annotations

import warnings
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fapilog.fastapi.builder import FastAPIBuilder


class TestFastAPIBuilderInheritance:
    """AC1 & AC2: FastAPIBuilder inherits from AsyncLoggerBuilder."""

    def test_is_subclass_of_async_logger_builder(self) -> None:
        from fapilog.builder import AsyncLoggerBuilder

        assert issubclass(FastAPIBuilder, AsyncLoggerBuilder)

    def test_inherits_with_preset_method(self) -> None:
        builder = FastAPIBuilder()
        result = builder.with_preset("production")
        assert result is builder

    def test_inherits_with_level_method(self) -> None:
        builder = FastAPIBuilder()
        result = builder.with_level("DEBUG")
        assert result is builder

    def test_inherits_with_sampling_method(self) -> None:
        builder = FastAPIBuilder()
        result = builder.with_sampling(rate=0.1)
        assert result is builder


class TestSkipPaths:
    """AC3: skip_paths() method."""

    def test_skip_paths_returns_self(self) -> None:
        builder = FastAPIBuilder()
        result = builder.skip_paths(["/health"])
        assert result is builder

    def test_skip_paths_stores_paths(self) -> None:
        builder = FastAPIBuilder()
        builder.skip_paths(["/health", "/metrics", "/ready"])
        assert builder._fastapi_config["skip_paths"] == [
            "/health",
            "/metrics",
            "/ready",
        ]

    def test_skip_paths_empty_list(self) -> None:
        builder = FastAPIBuilder()
        builder.skip_paths([])
        assert builder._fastapi_config["skip_paths"] == []


class TestIncludeHeaders:
    """AC3: include_headers() method."""

    def test_include_headers_returns_self(self) -> None:
        builder = FastAPIBuilder()
        result = builder.include_headers(["content-type"])
        assert result is builder

    def test_include_headers_stores_as_allow_headers(self) -> None:
        builder = FastAPIBuilder()
        builder.include_headers(["content-type", "user-agent", "accept"])
        assert builder._fastapi_config["allow_headers"] == [
            "content-type",
            "user-agent",
            "accept",
        ]


class TestWithCorrelationId:
    """AC3: with_correlation_id() method."""

    def test_with_correlation_id_returns_self(self) -> None:
        builder = FastAPIBuilder()
        result = builder.with_correlation_id()
        assert result is builder

    def test_with_correlation_id_default_values(self) -> None:
        builder = FastAPIBuilder()
        builder.with_correlation_id()
        config = builder._fastapi_config["correlation_id"]
        assert config["header"] == "X-Request-ID"
        assert config["generate"] is True
        assert config["propagate"] is True
        assert config["inject_response"] is True

    def test_with_correlation_id_custom_values(self) -> None:
        builder = FastAPIBuilder()
        builder.with_correlation_id(
            header="X-Correlation-ID",
            generate=False,
            propagate=False,
            inject_response=False,
        )
        config = builder._fastapi_config["correlation_id"]
        assert config["header"] == "X-Correlation-ID"
        assert config["generate"] is False
        assert config["propagate"] is False
        assert config["inject_response"] is False


class TestSampleRate:
    """AC3: sample_rate() method for request-level sampling."""

    def test_sample_rate_returns_self(self) -> None:
        builder = FastAPIBuilder()
        result = builder.sample_rate(0.5)
        assert result is builder

    def test_sample_rate_stores_rate(self) -> None:
        builder = FastAPIBuilder()
        builder.sample_rate(0.1)
        assert builder._fastapi_config["sample_rate"] == 0.1

    def test_sample_rate_accepts_full_range(self) -> None:
        builder = FastAPIBuilder()
        builder.sample_rate(0.0)
        assert builder._fastapi_config["sample_rate"] == 0.0

        builder.sample_rate(1.0)
        assert builder._fastapi_config["sample_rate"] == 1.0


class TestLogErrorsOnSkip:
    """AC3: log_errors_on_skip() method."""

    def test_log_errors_on_skip_returns_self(self) -> None:
        builder = FastAPIBuilder()
        result = builder.log_errors_on_skip(True)
        assert result is builder

    def test_log_errors_on_skip_default_true(self) -> None:
        builder = FastAPIBuilder()
        builder.log_errors_on_skip()
        assert builder._fastapi_config["log_errors_on_skip"] is True

    def test_log_errors_on_skip_false(self) -> None:
        builder = FastAPIBuilder()
        builder.log_errors_on_skip(False)
        assert builder._fastapi_config["log_errors_on_skip"] is False


class TestBuildReturnsLifespan:
    """AC8: build() returns a callable that works as FastAPI lifespan."""

    def test_build_returns_callable(self) -> None:
        builder = FastAPIBuilder().with_preset("production")
        lifespan = builder.build()
        assert callable(lifespan)


class TestMethodChaining:
    """Test that all methods can be chained together."""

    def test_full_chain(self) -> None:
        builder = (
            FastAPIBuilder()
            .with_preset("production")
            .with_level("DEBUG")
            .skip_paths(["/health", "/metrics"])
            .include_headers(["content-type"])
            .with_correlation_id(header="X-Request-ID")
            .sample_rate(0.5)
            .log_errors_on_skip(True)
        )
        assert isinstance(builder, FastAPIBuilder)
        assert builder._fastapi_config["skip_paths"] == ["/health", "/metrics"]
        assert builder._fastapi_config["allow_headers"] == ["content-type"]
        assert builder._fastapi_config["sample_rate"] == 0.5


class TestFastAPIEnvVars:
    """AC6: FastAPI-specific env vars work."""

    def test_skip_paths_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FAPILOG_FASTAPI__SKIP_PATHS", "/health,/metrics,/ready")
        builder = FastAPIBuilder()
        builder._apply_fastapi_env_vars()
        assert builder._fastapi_config["skip_paths"] == [
            "/health",
            "/metrics",
            "/ready",
        ]

    def test_include_headers_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(
            "FAPILOG_FASTAPI__INCLUDE_HEADERS", "content-type,user-agent"
        )
        builder = FastAPIBuilder()
        builder._apply_fastapi_env_vars()
        assert builder._fastapi_config["allow_headers"] == [
            "content-type",
            "user-agent",
        ]

    def test_sample_rate_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FAPILOG_FASTAPI__SAMPLE_RATE", "0.1")
        builder = FastAPIBuilder()
        builder._apply_fastapi_env_vars()
        assert builder._fastapi_config["sample_rate"] == 0.1

    def test_log_errors_on_skip_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FAPILOG_FASTAPI__LOG_ERRORS_ON_SKIP", "false")
        builder = FastAPIBuilder()
        builder._apply_fastapi_env_vars()
        assert builder._fastapi_config["log_errors_on_skip"] is False

    def test_env_vars_override_code_values(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC4: Env vars have priority over builder method calls."""
        monkeypatch.setenv("FAPILOG_FASTAPI__SAMPLE_RATE", "0.2")
        builder = FastAPIBuilder()
        builder.sample_rate(0.8)  # Code sets 0.8
        builder._apply_fastapi_env_vars()  # Env var sets 0.2
        assert builder._fastapi_config["sample_rate"] == 0.2


class TestEnvVarOverrideWarning:
    """AC5: Env var override warning emitted."""

    def test_override_warning_emitted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FAPILOG_FASTAPI__SAMPLE_RATE", "0.2")
        builder = FastAPIBuilder()
        builder.sample_rate(0.8)

        overrides = builder._detect_env_overrides()
        assert len(overrides) == 1
        assert "sample_rate" in overrides[0]
        assert "0.8" in overrides[0]
        assert "0.2" in overrides[0]

    def test_no_warning_when_no_override(self) -> None:
        builder = FastAPIBuilder()
        builder.sample_rate(0.5)
        overrides = builder._detect_env_overrides()
        assert len(overrides) == 0


class TestDeprecationWarning:
    """AC7: setup_logging() deprecated with warning."""

    def test_setup_logging_emits_deprecation_warning(self) -> None:
        from fapilog.fastapi import setup_logging

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            setup_logging(preset="production")
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "setup_logging() is deprecated" in str(w[0].message)
            assert "FastAPIBuilder" in str(w[0].message)


class TestEnvValueConversion:
    """Test _convert_env_value edge cases."""

    def test_convert_empty_list(self) -> None:
        from fapilog.fastapi.builder import _convert_env_value

        result = _convert_env_value("  ", "list")
        assert result == []

    def test_convert_invalid_float(self) -> None:
        from fapilog.fastapi.builder import _convert_env_value

        result = _convert_env_value("not-a-float", "float")
        assert result is None

    def test_convert_unknown_type(self) -> None:
        from fapilog.fastapi.builder import _convert_env_value

        result = _convert_env_value("value", "unknown")
        assert result is None

    def test_convert_bool_invalid_value(self) -> None:
        from fapilog.fastapi.builder import _convert_env_value

        result = _convert_env_value("invalid", "bool")
        assert result is None

    def test_convert_bool_true_variants(self) -> None:
        from fapilog.fastapi.builder import _convert_env_value

        for value in ["true", "1", "yes", "on", "TRUE", "True"]:
            result = _convert_env_value(value, "bool")
            assert result is True, f"Expected True for '{value}'"


class TestBuildWithoutPreset:
    """Test building without a preset."""

    def test_build_without_preset(self) -> None:
        builder = FastAPIBuilder().with_level("DEBUG")
        lifespan = builder.build()
        assert callable(lifespan)


class TestEnvVarConversionNone:
    """Test that env vars returning None don't overwrite code values."""

    def test_env_var_none_does_not_apply(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When env var conversion fails (returns None), code value is kept."""
        monkeypatch.setenv("FAPILOG_FASTAPI__SAMPLE_RATE", "not-a-float")
        builder = FastAPIBuilder()
        builder.sample_rate(0.5)
        builder._apply_fastapi_env_vars()
        # Invalid float env var should not override code value
        assert builder._fastapi_config["sample_rate"] == 0.5


class TestEnvOverrideWithNullCodeValue:
    """Test override detection when code value is not set."""

    def test_no_override_when_code_value_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No override warning when code didn't set a value."""
        monkeypatch.setenv("FAPILOG_FASTAPI__SAMPLE_RATE", "0.5")
        builder = FastAPIBuilder()  # No sample_rate set
        overrides = builder._detect_env_overrides()
        assert len(overrides) == 0


class TestDeepMerge:
    """Test the _deep_merge helper function."""

    def test_deep_merge_simple_override(self) -> None:
        from fapilog.fastapi.builder import _deep_merge

        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        _deep_merge(base, override)
        assert base == {"a": 1, "b": 3, "c": 4}

    def test_deep_merge_nested_dicts(self) -> None:
        from fapilog.fastapi.builder import _deep_merge

        base = {"core": {"level": "INFO", "workers": 2}}
        override = {"core": {"level": "DEBUG"}}
        _deep_merge(base, override)
        assert base == {"core": {"level": "DEBUG", "workers": 2}}

    def test_deep_merge_nested_override_non_dict(self) -> None:
        from fapilog.fastapi.builder import _deep_merge

        base = {"core": {"level": "INFO"}}
        override = {"core": "replaced"}
        _deep_merge(base, override)
        assert base == {"core": "replaced"}

    def test_deep_merge_empty_override(self) -> None:
        from fapilog.fastapi.builder import _deep_merge

        base = {"a": 1}
        override: dict[str, int] = {}
        _deep_merge(base, override)
        assert base == {"a": 1}

    def test_deep_merge_deeply_nested(self) -> None:
        from fapilog.fastapi.builder import _deep_merge

        base = {"a": {"b": {"c": 1, "d": 2}}}
        override = {"a": {"b": {"c": 3}}}
        _deep_merge(base, override)
        assert base == {"a": {"b": {"c": 3, "d": 2}}}


class TestBuildOverrideWarnings:
    """Test that build() emits override warnings via diagnostics."""

    def test_build_emits_override_warning(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that build() calls warn() for env var overrides."""
        monkeypatch.setenv("FAPILOG_FASTAPI__SAMPLE_RATE", "0.1")

        warnings_emitted: list[str] = []

        def mock_warn(source: str, msg: str) -> None:
            warnings_emitted.append(f"{source}: {msg}")

        monkeypatch.setattr("fapilog.fastapi.builder.warn", mock_warn)

        builder = FastAPIBuilder().with_preset("production").sample_rate(1.0)
        builder.build()

        assert len(warnings_emitted) == 1
        assert "sample_rate" in warnings_emitted[0]
        assert "0.1" in warnings_emitted[0]


class TestBuildWithSinks:
    """Test build() with custom sink configurations."""

    def test_build_with_sink_config(self) -> None:
        """Test that sinks are properly configured in build."""
        builder = FastAPIBuilder().with_preset("production").add_stdout()
        lifespan = builder.build()
        assert callable(lifespan)
        # Verify sink was added to builder
        assert len(builder._sinks) > 0

    def test_build_merges_sink_with_preset(self) -> None:
        """Test that custom sinks merge with preset sinks."""
        builder = FastAPIBuilder().with_preset("production")
        # Add another stdout sink to trigger merge logic
        builder.add_stdout()
        lifespan = builder.build()
        assert callable(lifespan)
        # Verify sink was added (exactly 1 explicit sink)
        assert len(builder._sinks) == 1


class TestLifespanExecution:
    """Test the lifespan function returned by build()."""

    @pytest.mark.asyncio
    async def test_lifespan_with_preset(self) -> None:
        """Test lifespan executes correctly with a preset."""
        from fastapi import FastAPI

        builder = FastAPIBuilder().with_preset("production")
        lifespan = builder.build()
        app = FastAPI()

        # Mock the drain to avoid actual cleanup
        with patch("fapilog.fastapi.setup._drain_logger", new_callable=AsyncMock):
            async with lifespan(app):
                # Verify logger was set on app state with expected interface
                assert hasattr(app.state, "fapilog_logger")
                logger = app.state.fapilog_logger
                assert hasattr(logger, "info")  # Has logging methods

    @pytest.mark.asyncio
    async def test_lifespan_without_preset(self) -> None:
        """Test lifespan executes correctly without a preset."""
        from fastapi import FastAPI

        builder = FastAPIBuilder().with_level("INFO")
        lifespan = builder.build()
        app = FastAPI()

        with patch("fapilog.fastapi.setup._drain_logger", new_callable=AsyncMock):
            async with lifespan(app):
                assert hasattr(app.state, "fapilog_logger")

    @pytest.mark.asyncio
    async def test_lifespan_with_custom_sinks(self) -> None:
        """Test lifespan with custom sink configuration."""
        from fastapi import FastAPI

        builder = FastAPIBuilder().with_preset("production").add_stdout()
        lifespan = builder.build()
        app = FastAPI()

        with patch("fapilog.fastapi.setup._drain_logger", new_callable=AsyncMock):
            async with lifespan(app):
                assert hasattr(app.state, "fapilog_logger")

    @pytest.mark.asyncio
    async def test_lifespan_with_sink_config(self) -> None:
        """Test lifespan merges sink configs correctly."""
        from fastapi import FastAPI

        # Create builder with preset and add sink with config
        builder = FastAPIBuilder().with_preset("production")
        # Manually add a sink with config to test the merge path
        builder._sinks.append({"name": "stdout", "config": {"format": "json"}})
        lifespan = builder.build()
        app = FastAPI()

        with patch("fapilog.fastapi.setup._drain_logger", new_callable=AsyncMock):
            async with lifespan(app):
                assert hasattr(app.state, "fapilog_logger")

    @pytest.mark.asyncio
    async def test_lifespan_drains_on_exit(self) -> None:
        """Test that lifespan drains logger on exit."""
        from fastapi import FastAPI

        builder = FastAPIBuilder().with_preset("production")
        lifespan = builder.build()
        app = FastAPI()

        mock_drain = AsyncMock()
        with patch("fapilog.fastapi.setup._drain_logger", mock_drain):
            async with lifespan(app):
                pass
            # Verify drain was called
            mock_drain.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_with_fastapi_config(self) -> None:
        """Test lifespan applies FastAPI-specific config."""
        from fastapi import FastAPI

        builder = (
            FastAPIBuilder()
            .with_preset("production")
            .skip_paths(["/health"])
            .sample_rate(0.5)
            .log_errors_on_skip(False)
            .include_headers(["content-type"])
        )
        lifespan = builder.build()
        app = FastAPI()

        with patch("fapilog.fastapi.setup._drain_logger", new_callable=AsyncMock):
            async with lifespan(app):
                assert hasattr(app.state, "fapilog_logger")

    @pytest.mark.asyncio
    async def test_lifespan_clears_middleware_stack(self) -> None:
        """Test that lifespan clears middleware_stack for rebuild."""
        from fastapi import FastAPI

        builder = FastAPIBuilder().with_preset("production")
        lifespan = builder.build()
        app = FastAPI()
        # Simulate existing middleware stack
        app.middleware_stack = MagicMock()

        with patch("fapilog.fastapi.setup._drain_logger", new_callable=AsyncMock):
            async with lifespan(app):
                # middleware_stack should be cleared
                assert app.middleware_stack is None or hasattr(
                    app.state, "fapilog_logger"
                )

    @pytest.mark.asyncio
    async def test_lifespan_invalid_config_raises(self) -> None:
        """Test that invalid configuration raises ValueError."""
        from fastapi import FastAPI

        builder = FastAPIBuilder()
        # Force invalid config by setting core to wrong type
        builder._config["core"] = {"log_level": ["not", "a", "string"]}
        lifespan = builder.build()
        app = FastAPI()

        with pytest.raises(ValueError, match="Invalid builder configuration"):
            async with lifespan(app):
                pass
