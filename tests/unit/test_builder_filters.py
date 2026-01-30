"""Unit tests for builder filter methods (Story 10.25)."""

from fapilog.builder import LoggerBuilder


class TestWithSampling:
    """Tests for with_sampling() method."""

    def test_with_sampling_adds_filter_and_config(self) -> None:
        """with_sampling() adds 'sampling' to filters and sets sample_rate."""
        builder = LoggerBuilder()
        builder.with_sampling(rate=0.1)

        filters = builder._config["core"]["filters"]
        filter_config = builder._config["filter_config"]["sampling"]

        assert "sampling" in filters
        assert filter_config["sample_rate"] == 0.1

    def test_with_sampling_with_seed(self) -> None:
        """with_sampling() can set optional seed for reproducibility."""
        builder = LoggerBuilder()
        builder.with_sampling(rate=0.5, seed=42)

        filter_config = builder._config["filter_config"]["sampling"]

        assert filter_config["sample_rate"] == 0.5
        assert filter_config["seed"] == 42

    def test_with_sampling_without_seed_omits_key(self) -> None:
        """with_sampling() omits seed key when not provided."""
        builder = LoggerBuilder()
        builder.with_sampling(rate=0.1)

        filter_config = builder._config["filter_config"]["sampling"]

        assert "seed" not in filter_config

    def test_with_sampling_returns_self(self) -> None:
        """with_sampling() returns self for chaining."""
        builder = LoggerBuilder()
        result = builder.with_sampling(rate=0.5)
        assert result is builder

    def test_with_sampling_default_rate(self) -> None:
        """with_sampling() uses default rate of 1.0 (keep all)."""
        builder = LoggerBuilder()
        builder.with_sampling()

        filter_config = builder._config["filter_config"]["sampling"]
        assert filter_config["sample_rate"] == 1.0

    def test_with_sampling_does_not_duplicate_filter(self) -> None:
        """Calling with_sampling() twice doesn't duplicate filter in list."""
        builder = LoggerBuilder()
        builder.with_sampling(rate=0.5)
        builder.with_sampling(rate=0.3)

        filters = builder._config["core"]["filters"]
        assert filters.count("sampling") == 1
        # Second call overwrites config
        assert builder._config["filter_config"]["sampling"]["sample_rate"] == 0.3

    def test_with_sampling_creates_valid_logger(self) -> None:
        """with_sampling() produces valid logger configuration."""
        logger = LoggerBuilder().with_sampling(rate=0.1, seed=42).add_stdout().build()
        assert callable(logger.info)


class TestWithAdaptiveSampling:
    """Tests for with_adaptive_sampling() method."""

    def test_with_adaptive_sampling_adds_filter_and_config(self) -> None:
        """with_adaptive_sampling() adds filter and sets all config fields."""
        builder = LoggerBuilder()
        builder.with_adaptive_sampling(
            min_rate=0.01,
            max_rate=1.0,
            target_events_per_sec=1000.0,
            window_seconds=60.0,
        )

        filters = builder._config["core"]["filters"]
        filter_config = builder._config["filter_config"]["adaptive_sampling"]

        assert "adaptive_sampling" in filters
        # Config keys must match AdaptiveSamplingConfig field names
        assert filter_config["min_sample_rate"] == 0.01
        assert filter_config["max_sample_rate"] == 1.0
        assert filter_config["target_eps"] == 1000.0
        assert filter_config["window_seconds"] == 60.0

    def test_with_adaptive_sampling_returns_self(self) -> None:
        """with_adaptive_sampling() returns self for chaining."""
        builder = LoggerBuilder()
        result = builder.with_adaptive_sampling()
        assert result is builder

    def test_with_adaptive_sampling_default_values(self) -> None:
        """with_adaptive_sampling() uses sensible defaults."""
        builder = LoggerBuilder()
        builder.with_adaptive_sampling()

        filter_config = builder._config["filter_config"]["adaptive_sampling"]

        # Config keys must match AdaptiveSamplingConfig field names
        assert filter_config["min_sample_rate"] == 0.01
        assert filter_config["max_sample_rate"] == 1.0
        assert filter_config["target_eps"] == 1000.0
        assert filter_config["window_seconds"] == 60.0

    def test_with_adaptive_sampling_does_not_duplicate_filter(self) -> None:
        """Calling with_adaptive_sampling() twice doesn't duplicate filter."""
        builder = LoggerBuilder()
        builder.with_adaptive_sampling(target_events_per_sec=500)
        builder.with_adaptive_sampling(target_events_per_sec=1000)

        filters = builder._config["core"]["filters"]
        assert filters.count("adaptive_sampling") == 1
        # Config key must match AdaptiveSamplingConfig field name
        assert (
            builder._config["filter_config"]["adaptive_sampling"]["target_eps"] == 1000
        )

    def test_with_adaptive_sampling_creates_valid_logger(self) -> None:
        """with_adaptive_sampling() produces valid logger configuration."""
        logger = (
            LoggerBuilder()
            .with_adaptive_sampling(
                min_rate=0.01, max_rate=1.0, target_events_per_sec=1000
            )
            .add_stdout()
            .build()
        )
        assert callable(logger.info)


class TestWithTraceSampling:
    """Tests for with_trace_sampling() method."""

    def test_with_trace_sampling_adds_filter_and_config(self) -> None:
        """with_trace_sampling() adds filter and sets config fields."""
        builder = LoggerBuilder()
        builder.with_trace_sampling(default_rate=0.1)

        filters = builder._config["core"]["filters"]
        filter_config = builder._config["filter_config"]["trace_sampling"]

        assert "trace_sampling" in filters
        # Config key must match TraceSamplingConfig field name
        assert filter_config["sample_rate"] == 0.1
        # honor_upstream not in TraceSamplingConfig - should not be in config
        assert "honor_upstream" not in filter_config

    def test_with_trace_sampling_returns_self(self) -> None:
        """with_trace_sampling() returns self for chaining."""
        builder = LoggerBuilder()
        result = builder.with_trace_sampling()
        assert result is builder

    def test_with_trace_sampling_default_values(self) -> None:
        """with_trace_sampling() uses sensible defaults."""
        builder = LoggerBuilder()
        builder.with_trace_sampling()

        filter_config = builder._config["filter_config"]["trace_sampling"]

        # Config key must match TraceSamplingConfig field name
        assert filter_config["sample_rate"] == 1.0
        # honor_upstream not in TraceSamplingConfig
        assert "honor_upstream" not in filter_config

    def test_with_trace_sampling_does_not_duplicate_filter(self) -> None:
        """Calling with_trace_sampling() twice doesn't duplicate filter."""
        builder = LoggerBuilder()
        builder.with_trace_sampling(default_rate=0.5)
        builder.with_trace_sampling(default_rate=0.3)

        filters = builder._config["core"]["filters"]
        assert filters.count("trace_sampling") == 1
        # Config key must match TraceSamplingConfig field name
        assert builder._config["filter_config"]["trace_sampling"]["sample_rate"] == 0.3

    def test_with_trace_sampling_creates_valid_logger(self) -> None:
        """with_trace_sampling() produces valid logger configuration."""
        logger = (
            LoggerBuilder().with_trace_sampling(default_rate=0.1).add_stdout().build()
        )
        assert callable(logger.info)


class TestWithRateLimit:
    """Tests for with_rate_limit() method."""

    def test_with_rate_limit_adds_filter_and_config(self) -> None:
        """with_rate_limit() adds filter and sets all config fields."""
        builder = LoggerBuilder()
        builder.with_rate_limit(
            capacity=100,
            refill_rate=10.0,
            key_field="user_id",
            max_keys=5000,
            overflow_action="mark",
        )

        filters = builder._config["core"]["filters"]
        filter_config = builder._config["filter_config"]["rate_limit"]

        assert "rate_limit" in filters
        assert filter_config["capacity"] == 100
        assert filter_config["refill_rate_per_sec"] == 10.0
        assert filter_config["key_field"] == "user_id"
        assert filter_config["max_keys"] == 5000
        assert filter_config["overflow_action"] == "mark"

    def test_with_rate_limit_returns_self(self) -> None:
        """with_rate_limit() returns self for chaining."""
        builder = LoggerBuilder()
        result = builder.with_rate_limit()
        assert result is builder

    def test_with_rate_limit_default_values(self) -> None:
        """with_rate_limit() uses sensible defaults."""
        builder = LoggerBuilder()
        builder.with_rate_limit()

        filter_config = builder._config["filter_config"]["rate_limit"]

        assert filter_config["capacity"] == 10
        assert filter_config["refill_rate_per_sec"] == 5.0
        assert filter_config["max_keys"] == 10000
        assert filter_config["overflow_action"] == "drop"
        assert "key_field" not in filter_config

    def test_with_rate_limit_without_key_field_omits_key(self) -> None:
        """with_rate_limit() omits key_field when not provided."""
        builder = LoggerBuilder()
        builder.with_rate_limit(capacity=50)

        filter_config = builder._config["filter_config"]["rate_limit"]
        assert "key_field" not in filter_config

    def test_with_rate_limit_does_not_duplicate_filter(self) -> None:
        """Calling with_rate_limit() twice doesn't duplicate filter."""
        builder = LoggerBuilder()
        builder.with_rate_limit(capacity=50)
        builder.with_rate_limit(capacity=100)

        filters = builder._config["core"]["filters"]
        assert filters.count("rate_limit") == 1
        assert builder._config["filter_config"]["rate_limit"]["capacity"] == 100

    def test_with_rate_limit_creates_valid_logger(self) -> None:
        """with_rate_limit() produces valid logger configuration."""
        logger = (
            LoggerBuilder()
            .with_rate_limit(capacity=100, refill_rate=10.0, overflow_action="drop")
            .add_stdout()
            .build()
        )
        assert callable(logger.info)


class TestWithFirstOccurrence:
    """Tests for with_first_occurrence() method."""

    def test_with_first_occurrence_adds_filter_and_config(self) -> None:
        """with_first_occurrence() adds filter and sets all config fields."""
        builder = LoggerBuilder()
        builder.with_first_occurrence(
            window_seconds=60.0,
            max_keys=5000,
            key_fields=["message", "level"],
        )

        filters = builder._config["core"]["filters"]
        filter_config = builder._config["filter_config"]["first_occurrence"]

        assert "first_occurrence" in filters
        assert filter_config["window_seconds"] == 60.0
        assert filter_config["max_keys"] == 5000
        assert filter_config["key_fields"] == ["message", "level"]

    def test_with_first_occurrence_returns_self(self) -> None:
        """with_first_occurrence() returns self for chaining."""
        builder = LoggerBuilder()
        result = builder.with_first_occurrence()
        assert result is builder

    def test_with_first_occurrence_default_values(self) -> None:
        """with_first_occurrence() uses sensible defaults."""
        builder = LoggerBuilder()
        builder.with_first_occurrence()

        filter_config = builder._config["filter_config"]["first_occurrence"]

        assert filter_config["window_seconds"] == 300.0
        assert filter_config["max_keys"] == 10000
        assert "key_fields" not in filter_config

    def test_with_first_occurrence_without_key_fields_omits_key(self) -> None:
        """with_first_occurrence() omits key_fields when not provided."""
        builder = LoggerBuilder()
        builder.with_first_occurrence(window_seconds=60.0)

        filter_config = builder._config["filter_config"]["first_occurrence"]
        assert "key_fields" not in filter_config

    def test_with_first_occurrence_does_not_duplicate_filter(self) -> None:
        """Calling with_first_occurrence() twice doesn't duplicate filter."""
        builder = LoggerBuilder()
        builder.with_first_occurrence(window_seconds=60.0)
        builder.with_first_occurrence(window_seconds=120.0)

        filters = builder._config["core"]["filters"]
        assert filters.count("first_occurrence") == 1
        assert (
            builder._config["filter_config"]["first_occurrence"]["window_seconds"]
            == 120.0
        )

    def test_with_first_occurrence_creates_valid_logger(self) -> None:
        """with_first_occurrence() produces valid logger configuration."""
        logger = (
            LoggerBuilder()
            .with_first_occurrence(window_seconds=60.0, max_keys=5000)
            .add_stdout()
            .build()
        )
        assert callable(logger.info)

    def test_with_first_occurrence_uses_max_keys(self) -> None:
        """with_first_occurrence() uses max_keys (not max_entries) in config."""
        builder = LoggerBuilder()
        builder.with_first_occurrence(window_seconds=60.0, max_keys=500)

        filter_config = builder._config["filter_config"]["first_occurrence"]

        assert "max_keys" in filter_config
        assert filter_config["max_keys"] == 500
        assert "max_entries" not in filter_config

    def test_with_first_occurrence_max_entries_deprecated(self) -> None:
        """with_first_occurrence() emits deprecation warning for max_entries."""
        import warnings

        builder = LoggerBuilder()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            builder.with_first_occurrence(window_seconds=60.0, max_entries=500)

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "max_entries" in str(w[0].message)
            assert "max_keys" in str(w[0].message)

    def test_with_first_occurrence_max_entries_maps_to_max_keys(self) -> None:
        """with_first_occurrence() maps deprecated max_entries to max_keys."""
        import warnings

        builder = LoggerBuilder()
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            builder.with_first_occurrence(window_seconds=60.0, max_entries=500)

        filter_config = builder._config["filter_config"]["first_occurrence"]

        assert filter_config.get("max_keys") == 500
        assert "max_entries" not in filter_config


class TestFiltersAndProcessorsChainable:
    """Tests for AC6: Multiple filters and processors can be chained."""

    def test_all_filter_methods_chainable(self) -> None:
        """All filter builder methods can be chained together."""
        builder = LoggerBuilder()
        result = (
            builder.with_sampling(rate=0.5)
            .with_adaptive_sampling(target_events_per_sec=500)
            .with_trace_sampling(default_rate=0.1)
            .with_rate_limit(capacity=100)
            .with_first_occurrence(window_seconds=60)
        )
        assert result is builder

        # Verify all filters are in the list
        filters = builder._config["core"]["filters"]
        assert "sampling" in filters
        assert "adaptive_sampling" in filters
        assert "trace_sampling" in filters
        assert "rate_limit" in filters
        assert "first_occurrence" in filters

    def test_filters_and_processor_chainable(self) -> None:
        """Filters and size_guard processor can be chained together."""
        builder = LoggerBuilder()
        result = (
            builder.with_sampling(rate=0.5)
            .with_rate_limit(capacity=1000)
            .with_size_guard(max_bytes="1 MB")
        )
        assert result is builder

        filters = builder._config["core"]["filters"]
        processors = builder._config["core"]["processors"]
        assert "sampling" in filters
        assert "rate_limit" in filters
        assert "size_guard" in processors

    def test_full_chain_creates_valid_logger(self) -> None:
        """Full chain of filters and processor produces valid logger (AC6)."""
        logger = (
            LoggerBuilder()
            .with_level("INFO")
            .with_sampling(rate=0.5)
            .with_rate_limit(capacity=1000)
            .with_size_guard(max_bytes="1 MB")
            .add_stdout()
            .build()
        )
        assert callable(logger.info)

    def test_chain_with_sink_and_redaction(self) -> None:
        """Filters chain with sinks and redaction."""
        logger = (
            LoggerBuilder()
            .with_level("DEBUG")
            .with_sampling(rate=0.1, seed=42)
            .with_first_occurrence(window_seconds=60.0)
            .with_size_guard(max_bytes="256 KB", action="truncate")
            .with_redaction(fields=["password", "ssn"])
            .add_stdout(format="json")
            .build()
        )
        assert callable(logger.info)
