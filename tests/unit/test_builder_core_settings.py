"""Unit tests for builder CoreSettings methods (Story 10.23)."""

from fapilog.builder import LoggerBuilder


class TestWithCircuitBreaker:
    """Tests for with_circuit_breaker() method."""

    def test_with_circuit_breaker_sets_all_fields(self) -> None:
        """with_circuit_breaker() sets enabled, threshold, and timeout."""
        builder = LoggerBuilder()
        builder.with_circuit_breaker(
            enabled=True,
            failure_threshold=3,
            recovery_timeout=60.0,
        )

        core = builder._config["core"]
        assert core["sink_circuit_breaker_enabled"] is True
        assert core["sink_circuit_breaker_failure_threshold"] == 3
        assert core["sink_circuit_breaker_recovery_timeout_seconds"] == 60.0

    def test_with_circuit_breaker_parses_string_duration(self) -> None:
        """with_circuit_breaker() parses human-readable duration strings."""
        builder = LoggerBuilder()
        builder.with_circuit_breaker(recovery_timeout="30s")

        core = builder._config["core"]
        assert core["sink_circuit_breaker_recovery_timeout_seconds"] == 30.0

    def test_with_circuit_breaker_parses_milliseconds(self) -> None:
        """with_circuit_breaker() parses millisecond duration strings (Story 10.37 AC5)."""
        builder = LoggerBuilder()
        builder.with_circuit_breaker(recovery_timeout="500ms")

        core = builder._config["core"]
        assert core["sink_circuit_breaker_recovery_timeout_seconds"] == 0.5

    def test_with_circuit_breaker_parses_decimal_duration(self) -> None:
        """with_circuit_breaker() parses decimal duration strings (Story 10.37 AC5)."""
        builder = LoggerBuilder()
        builder.with_circuit_breaker(recovery_timeout="1.5s")

        core = builder._config["core"]
        assert core["sink_circuit_breaker_recovery_timeout_seconds"] == 1.5

    def test_with_circuit_breaker_returns_self(self) -> None:
        """with_circuit_breaker() returns self for chaining."""
        builder = LoggerBuilder()
        result = builder.with_circuit_breaker()
        assert result is builder

    def test_with_circuit_breaker_default_values(self) -> None:
        """with_circuit_breaker() uses sensible defaults."""
        builder = LoggerBuilder()
        builder.with_circuit_breaker()

        core = builder._config["core"]
        assert core["sink_circuit_breaker_enabled"] is True
        assert core["sink_circuit_breaker_failure_threshold"] == 5
        assert core["sink_circuit_breaker_recovery_timeout_seconds"] == 30.0

    def test_with_circuit_breaker_creates_valid_logger(self) -> None:
        """with_circuit_breaker() produces valid logger configuration."""
        logger = (
            LoggerBuilder()
            .with_circuit_breaker(enabled=True, failure_threshold=5)
            .add_stdout()
            .build()
        )
        assert callable(logger.info)


class TestWithBackpressure:
    """Tests for with_backpressure() method."""

    def test_with_backpressure_sets_fields(self) -> None:
        """with_backpressure() sets wait_ms and drop_on_full."""
        builder = LoggerBuilder()
        builder.with_backpressure(wait_ms=100, drop_on_full=False)

        core = builder._config["core"]
        assert core["backpressure_wait_ms"] == 100
        assert core["drop_on_full"] is False

    def test_with_backpressure_returns_self(self) -> None:
        """with_backpressure() returns self for chaining."""
        builder = LoggerBuilder()
        result = builder.with_backpressure()
        assert result is builder

    def test_with_backpressure_default_values(self) -> None:
        """with_backpressure() uses sensible defaults."""
        builder = LoggerBuilder()
        builder.with_backpressure()

        core = builder._config["core"]
        assert core["backpressure_wait_ms"] == 50
        assert core["drop_on_full"] is True

    def test_with_backpressure_creates_valid_logger(self) -> None:
        """with_backpressure() produces valid logger configuration."""
        logger = (
            LoggerBuilder()
            .with_backpressure(wait_ms=100, drop_on_full=False)
            .add_stdout()
            .build()
        )
        assert callable(logger.info)


class TestWithWorkers:
    """Tests for with_workers() method."""

    def test_with_workers_sets_count(self) -> None:
        """with_workers() sets worker_count."""
        builder = LoggerBuilder()
        builder.with_workers(count=4)

        core = builder._config["core"]
        assert core["worker_count"] == 4

    def test_with_workers_returns_self(self) -> None:
        """with_workers() returns self for chaining."""
        builder = LoggerBuilder()
        result = builder.with_workers(count=2)
        assert result is builder

    def test_with_workers_default_value(self) -> None:
        """with_workers() uses default of 1."""
        builder = LoggerBuilder()
        builder.with_workers()

        core = builder._config["core"]
        assert core["worker_count"] == 1

    def test_with_workers_creates_valid_logger(self) -> None:
        """with_workers() produces valid logger configuration."""
        logger = LoggerBuilder().with_workers(count=4).add_stdout().build()
        assert callable(logger.info)


class TestWithShutdownTimeout:
    """Tests for with_shutdown_timeout() method."""

    def test_with_shutdown_timeout_sets_field(self) -> None:
        """with_shutdown_timeout() sets shutdown_timeout_seconds."""
        builder = LoggerBuilder()
        builder.with_shutdown_timeout(timeout=5.0)

        core = builder._config["core"]
        assert core["shutdown_timeout_seconds"] == 5.0

    def test_with_shutdown_timeout_parses_string(self) -> None:
        """with_shutdown_timeout() parses human-readable strings."""
        builder = LoggerBuilder()
        builder.with_shutdown_timeout(timeout="10s")

        core = builder._config["core"]
        assert core["shutdown_timeout_seconds"] == 10.0

    def test_with_shutdown_timeout_returns_self(self) -> None:
        """with_shutdown_timeout() returns self for chaining."""
        builder = LoggerBuilder()
        result = builder.with_shutdown_timeout()
        assert result is builder

    def test_with_shutdown_timeout_default_value(self) -> None:
        """with_shutdown_timeout() uses default of 3s."""
        builder = LoggerBuilder()
        builder.with_shutdown_timeout()

        core = builder._config["core"]
        assert core["shutdown_timeout_seconds"] == 3.0


class TestWithExceptions:
    """Tests for with_exceptions() method."""

    def test_with_exceptions_sets_all_fields(self) -> None:
        """with_exceptions() sets enabled, max_frames, and max_stack_chars."""
        builder = LoggerBuilder()
        builder.with_exceptions(
            enabled=True,
            max_frames=20,
            max_stack_chars=50000,
        )

        core = builder._config["core"]
        assert core["exceptions_enabled"] is True
        assert core["exceptions_max_frames"] == 20
        assert core["exceptions_max_stack_chars"] == 50000

    def test_with_exceptions_returns_self(self) -> None:
        """with_exceptions() returns self for chaining."""
        builder = LoggerBuilder()
        result = builder.with_exceptions()
        assert result is builder

    def test_with_exceptions_default_values(self) -> None:
        """with_exceptions() uses sensible defaults."""
        builder = LoggerBuilder()
        builder.with_exceptions()

        core = builder._config["core"]
        assert core["exceptions_enabled"] is True
        assert core["exceptions_max_frames"] == 10
        assert core["exceptions_max_stack_chars"] == 20000

    def test_with_exceptions_creates_valid_logger(self) -> None:
        """with_exceptions() produces valid logger configuration."""
        logger = LoggerBuilder().with_exceptions(max_frames=15).add_stdout().build()
        assert callable(logger.info)


class TestWithParallelSinkWrites:
    """Tests for with_parallel_sink_writes() method."""

    def test_with_parallel_sink_writes_sets_field(self) -> None:
        """with_parallel_sink_writes() sets sink_parallel_writes."""
        builder = LoggerBuilder()
        builder.with_parallel_sink_writes(enabled=True)

        core = builder._config["core"]
        assert core["sink_parallel_writes"] is True

    def test_with_parallel_sink_writes_returns_self(self) -> None:
        """with_parallel_sink_writes() returns self for chaining."""
        builder = LoggerBuilder()
        result = builder.with_parallel_sink_writes()
        assert result is builder

    def test_with_parallel_sink_writes_default_true(self) -> None:
        """with_parallel_sink_writes() defaults to True."""
        builder = LoggerBuilder()
        builder.with_parallel_sink_writes()

        core = builder._config["core"]
        assert core["sink_parallel_writes"] is True


class TestWithMetrics:
    """Tests for with_metrics() method."""

    def test_with_metrics_sets_field(self) -> None:
        """with_metrics() sets enable_metrics."""
        builder = LoggerBuilder()
        builder.with_metrics(enabled=True)

        core = builder._config["core"]
        assert core["enable_metrics"] is True

    def test_with_metrics_returns_self(self) -> None:
        """with_metrics() returns self for chaining."""
        builder = LoggerBuilder()
        result = builder.with_metrics()
        assert result is builder

    def test_with_metrics_default_true(self) -> None:
        """with_metrics() defaults to True."""
        builder = LoggerBuilder()
        builder.with_metrics()

        core = builder._config["core"]
        assert core["enable_metrics"] is True


class TestWithErrorDeduplication:
    """Tests for with_error_deduplication() method."""

    def test_with_error_deduplication_sets_field(self) -> None:
        """with_error_deduplication() sets error_dedupe_window_seconds."""
        builder = LoggerBuilder()
        builder.with_error_deduplication(window_seconds=10.0)

        core = builder._config["core"]
        assert core["error_dedupe_window_seconds"] == 10.0

    def test_with_error_deduplication_returns_self(self) -> None:
        """with_error_deduplication() returns self for chaining."""
        builder = LoggerBuilder()
        result = builder.with_error_deduplication()
        assert result is builder

    def test_with_error_deduplication_default_value(self) -> None:
        """with_error_deduplication() uses default of 5.0."""
        builder = LoggerBuilder()
        builder.with_error_deduplication()

        core = builder._config["core"]
        assert core["error_dedupe_window_seconds"] == 5.0


class TestWithDiagnostics:
    """Tests for with_diagnostics() method."""

    def test_with_diagnostics_sets_all_fields(self) -> None:
        """with_diagnostics() sets enabled and output."""
        builder = LoggerBuilder()
        builder.with_diagnostics(enabled=True, output="stdout")

        core = builder._config["core"]
        assert core["internal_logging_enabled"] is True
        assert core["diagnostics_output"] == "stdout"

    def test_with_diagnostics_returns_self(self) -> None:
        """with_diagnostics() returns self for chaining."""
        builder = LoggerBuilder()
        result = builder.with_diagnostics()
        assert result is builder

    def test_with_diagnostics_default_values(self) -> None:
        """with_diagnostics() uses sensible defaults."""
        builder = LoggerBuilder()
        builder.with_diagnostics()

        core = builder._config["core"]
        assert core["internal_logging_enabled"] is True
        assert core["diagnostics_output"] == "stderr"


class TestWithAppName:
    """Tests for with_app_name() method."""

    def test_with_app_name_sets_field(self) -> None:
        """with_app_name() sets app_name."""
        builder = LoggerBuilder()
        builder.with_app_name(name="my-service")

        core = builder._config["core"]
        assert core["app_name"] == "my-service"

    def test_with_app_name_returns_self(self) -> None:
        """with_app_name() returns self for chaining."""
        builder = LoggerBuilder()
        result = builder.with_app_name(name="test")
        assert result is builder


class TestWithStrictMode:
    """Tests for with_strict_mode() method."""

    def test_with_strict_mode_sets_field(self) -> None:
        """with_strict_mode() sets strict_envelope_mode."""
        builder = LoggerBuilder()
        builder.with_strict_mode(enabled=True)

        core = builder._config["core"]
        assert core["strict_envelope_mode"] is True

    def test_with_strict_mode_returns_self(self) -> None:
        """with_strict_mode() returns self for chaining."""
        builder = LoggerBuilder()
        result = builder.with_strict_mode()
        assert result is builder

    def test_with_strict_mode_default_true(self) -> None:
        """with_strict_mode() defaults to True."""
        builder = LoggerBuilder()
        builder.with_strict_mode()

        core = builder._config["core"]
        assert core["strict_envelope_mode"] is True


class TestWithUnhandledExceptionCapture:
    """Tests for with_unhandled_exception_capture() method."""

    def test_with_unhandled_exception_capture_sets_field(self) -> None:
        """with_unhandled_exception_capture() sets capture_unhandled_enabled."""
        builder = LoggerBuilder()
        builder.with_unhandled_exception_capture(enabled=True)

        core = builder._config["core"]
        assert core["capture_unhandled_enabled"] is True

    def test_with_unhandled_exception_capture_returns_self(self) -> None:
        """with_unhandled_exception_capture() returns self for chaining."""
        builder = LoggerBuilder()
        result = builder.with_unhandled_exception_capture()
        assert result is builder

    def test_with_unhandled_exception_capture_default_true(self) -> None:
        """with_unhandled_exception_capture() defaults to True."""
        builder = LoggerBuilder()
        builder.with_unhandled_exception_capture()

        core = builder._config["core"]
        assert core["capture_unhandled_enabled"] is True


class TestAllMethodsChainable:
    """Tests for AC6: All new methods return Self for fluent chaining."""

    def test_all_core_settings_methods_are_chainable(self) -> None:
        """All new CoreSettings methods can be chained together."""
        logger = (
            LoggerBuilder()
            .with_level("INFO")
            .with_circuit_breaker(enabled=True)
            .with_backpressure(wait_ms=50)
            .with_workers(count=2)
            .with_shutdown_timeout("5s")
            .with_exceptions(max_frames=15)
            .with_parallel_sink_writes(enabled=True)
            .with_metrics(enabled=True)
            .with_error_deduplication(window_seconds=10.0)
            .with_diagnostics(enabled=False)
            .with_app_name(name="test-app")
            .with_strict_mode(enabled=True)
            .with_unhandled_exception_capture(enabled=True)
            .add_stdout()
            .build()
        )
        assert callable(logger.info)


class TestBuilderSettingsEquivalence:
    """Tests for Settings equivalence per AC1-AC5."""

    def test_circuit_breaker_matches_settings(self) -> None:
        """Builder produces same Settings as direct Settings construction (AC1)."""
        from fapilog.core.settings import CoreSettings, Settings

        # Build via builder
        builder = LoggerBuilder()
        builder.with_circuit_breaker(
            enabled=True,
            failure_threshold=5,
            recovery_timeout="30s",
        )

        # Build via Settings
        expected_settings = Settings(
            core=CoreSettings(
                sink_circuit_breaker_enabled=True,
                sink_circuit_breaker_failure_threshold=5,
                sink_circuit_breaker_recovery_timeout_seconds=30.0,
            )
        )

        assert builder._config["core"]["sink_circuit_breaker_enabled"] == (
            expected_settings.core.sink_circuit_breaker_enabled
        )
        assert builder._config["core"]["sink_circuit_breaker_failure_threshold"] == (
            expected_settings.core.sink_circuit_breaker_failure_threshold
        )
        assert builder._config["core"][
            "sink_circuit_breaker_recovery_timeout_seconds"
        ] == (expected_settings.core.sink_circuit_breaker_recovery_timeout_seconds)

    def test_backpressure_matches_settings(self) -> None:
        """Builder produces same Settings as direct Settings construction (AC2)."""
        from fapilog.core.settings import CoreSettings, Settings

        builder = LoggerBuilder()
        builder.with_backpressure(wait_ms=100, drop_on_full=False)

        expected_settings = Settings(
            core=CoreSettings(
                backpressure_wait_ms=100,
                drop_on_full=False,
            )
        )

        assert builder._config["core"]["backpressure_wait_ms"] == (
            expected_settings.core.backpressure_wait_ms
        )
        assert builder._config["core"]["drop_on_full"] == (
            expected_settings.core.drop_on_full
        )

    def test_workers_and_shutdown_match_settings(self) -> None:
        """Builder produces same Settings for workers/shutdown (AC3)."""
        from fapilog.core.settings import CoreSettings, Settings

        builder = LoggerBuilder()
        builder.with_workers(count=4)
        builder.with_shutdown_timeout("5s")

        expected_settings = Settings(
            core=CoreSettings(
                worker_count=4,
                shutdown_timeout_seconds=5.0,
            )
        )

        assert builder._config["core"]["worker_count"] == (
            expected_settings.core.worker_count
        )
        assert builder._config["core"]["shutdown_timeout_seconds"] == (
            expected_settings.core.shutdown_timeout_seconds
        )

    def test_exceptions_match_settings(self) -> None:
        """Builder produces same Settings for exceptions (AC4)."""
        from fapilog.core.settings import CoreSettings, Settings

        builder = LoggerBuilder()
        builder.with_exceptions(
            enabled=True,
            max_frames=20,
            max_stack_chars=50000,
        )

        expected_settings = Settings(
            core=CoreSettings(
                exceptions_enabled=True,
                exceptions_max_frames=20,
                exceptions_max_stack_chars=50000,
            )
        )

        assert builder._config["core"]["exceptions_enabled"] == (
            expected_settings.core.exceptions_enabled
        )
        assert builder._config["core"]["exceptions_max_frames"] == (
            expected_settings.core.exceptions_max_frames
        )
        assert builder._config["core"]["exceptions_max_stack_chars"] == (
            expected_settings.core.exceptions_max_stack_chars
        )

    def test_performance_match_settings(self) -> None:
        """Builder produces same Settings for performance options (AC5)."""
        from fapilog.core.settings import CoreSettings, Settings

        builder = LoggerBuilder()
        builder.with_parallel_sink_writes(enabled=True)
        builder.with_metrics(enabled=True)

        expected_settings = Settings(
            core=CoreSettings(
                sink_parallel_writes=True,
                enable_metrics=True,
            )
        )

        assert builder._config["core"]["sink_parallel_writes"] == (
            expected_settings.core.sink_parallel_writes
        )
        assert builder._config["core"]["enable_metrics"] == (
            expected_settings.core.enable_metrics
        )
