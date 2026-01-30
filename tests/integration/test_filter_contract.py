"""Contract tests for filter/processor builder methods (Story 12.28).

These tests verify that builder methods generate config that is accepted
by the plugin config classes (which reject unknown fields).
"""

import tempfile

import pytest

from fapilog import Settings, _build_pipeline_impl, _load_plugins
from fapilog.builder import AsyncLoggerBuilder, LoggerBuilder


class TestFilterContractTests:
    """Contract tests verifying builder output matches plugin config expectations."""

    @pytest.mark.parametrize(
        "filter_name,builder_call",
        [
            ("sampling", lambda b: b.with_sampling(rate=0.5)),
            (
                "adaptive_sampling",
                lambda b: b.with_adaptive_sampling(
                    min_rate=0.01, max_rate=1.0, target_events_per_sec=500
                ),
            ),
            ("trace_sampling", lambda b: b.with_trace_sampling(default_rate=0.5)),
            ("rate_limit", lambda b: b.with_rate_limit(capacity=100)),
            ("first_occurrence", lambda b: b.with_first_occurrence(window_seconds=60)),
        ],
    )
    def test_filter_loads_via_builder(
        self, filter_name: str, builder_call: callable
    ) -> None:
        """Builder-generated config loads successfully via _build_pipeline."""
        builder = builder_call(LoggerBuilder())

        settings = Settings(
            core=builder._config.get("core"),
            filter_config=builder._config.get("filter_config"),
        )

        _, _, _, _, filters, _ = _build_pipeline_impl(settings, _load_plugins)

        assert len(filters) == 1
        assert filters[0].name == filter_name


class TestProcessorContractTests:
    """Contract tests for processor builder methods."""

    def test_size_guard_loads_via_builder(self) -> None:
        """with_size_guard() config loads successfully in pipeline."""
        builder = LoggerBuilder().with_size_guard(max_bytes="1 MB")

        settings = Settings(
            core=builder._config.get("core"),
            processor_config=builder._config.get("processor_config"),
        )

        _, _, _, processors, _, _ = _build_pipeline_impl(settings, _load_plugins)

        assert len(processors) == 1
        assert processors[0].name == "size_guard"


class TestAdaptiveSamplingConfigContract:
    """Contract tests for adaptive_sampling config keys matching plugin."""

    def test_adaptive_sampling_config_keys_match_plugin(self) -> None:
        """with_adaptive_sampling() generates config matching AdaptiveSamplingConfig."""
        builder = LoggerBuilder().with_adaptive_sampling(
            min_rate=0.01, max_rate=1.0, target_events_per_sec=500, window_seconds=30
        )
        config = builder._config["filter_config"]["adaptive_sampling"]

        # These must match AdaptiveSamplingConfig field names
        assert "min_sample_rate" in config
        assert "max_sample_rate" in config
        assert "target_eps" in config
        assert "window_seconds" in config

        # Old keys must NOT be present
        assert "min_rate" not in config
        assert "max_rate" not in config
        assert "target_events_per_sec" not in config


class TestTraceSamplingConfigContract:
    """Contract tests for trace_sampling config keys matching plugin."""

    def test_trace_sampling_config_keys_match_plugin(self) -> None:
        """with_trace_sampling() generates config matching TraceSamplingConfig."""
        builder = LoggerBuilder().with_trace_sampling(default_rate=0.1)
        config = builder._config["filter_config"]["trace_sampling"]

        # Must match TraceSamplingConfig field names
        assert "sample_rate" in config

        # Old/invalid keys must NOT be present
        assert "default_rate" not in config
        assert "honor_upstream" not in config


class TestAllFiltersSmoke:
    """Smoke test that exercises all filter methods together."""

    @pytest.mark.asyncio
    async def test_all_filters_load_when_chained(self) -> None:
        """All filter methods can be chained and all filters load successfully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = await (
                AsyncLoggerBuilder()
                .with_sampling(rate=0.9)
                .with_adaptive_sampling(target_events_per_sec=1000)
                .with_trace_sampling(default_rate=0.5)
                .with_rate_limit(capacity=100)
                .with_first_occurrence(window_seconds=60)
                .with_size_guard(max_bytes="1 MB")
                .add_file(directory=tmpdir)
                .reuse(False)
                .build_async()
            )

            # Verify logger works - log a message and drain
            await logger.info("test message for smoke test")
            await logger.drain()

            # Verify logger has the expected callable interface
            assert callable(logger.info)
            assert callable(logger.debug)
            assert callable(logger.warning)
            assert callable(logger.error)

    def test_all_filters_config_generated_correctly(self) -> None:
        """All filter builder methods generate valid config dictionaries."""
        builder = (
            LoggerBuilder()
            .with_sampling(rate=0.9)
            .with_adaptive_sampling(
                min_rate=0.01, max_rate=1.0, target_events_per_sec=1000
            )
            .with_trace_sampling(default_rate=0.5)
            .with_rate_limit(capacity=100, refill_rate=10.0)
            .with_first_occurrence(window_seconds=60, max_keys=5000)
            .with_size_guard(max_bytes="1 MB", action="truncate")
        )

        # Verify all filters are registered
        filters = builder._config["core"]["filters"]
        assert "sampling" in filters
        assert "adaptive_sampling" in filters
        assert "trace_sampling" in filters
        assert "rate_limit" in filters
        assert "first_occurrence" in filters

        # Verify processor is registered
        processors = builder._config["core"]["processors"]
        assert "size_guard" in processors

        # Verify all filter configs use correct keys
        filter_config = builder._config["filter_config"]

        # sampling
        assert filter_config["sampling"]["sample_rate"] == 0.9

        # adaptive_sampling - uses plugin field names
        assert filter_config["adaptive_sampling"]["min_sample_rate"] == 0.01
        assert filter_config["adaptive_sampling"]["max_sample_rate"] == 1.0
        assert filter_config["adaptive_sampling"]["target_eps"] == 1000

        # trace_sampling - uses plugin field name
        assert filter_config["trace_sampling"]["sample_rate"] == 0.5

        # rate_limit
        assert filter_config["rate_limit"]["capacity"] == 100
        assert filter_config["rate_limit"]["refill_rate_per_sec"] == 10.0

        # first_occurrence
        assert filter_config["first_occurrence"]["window_seconds"] == 60
        assert filter_config["first_occurrence"]["max_keys"] == 5000

        # Verify processor config
        processor_config = builder._config["processor_config"]
        assert processor_config["size_guard"]["max_bytes"] == "1 MB"
        assert processor_config["size_guard"]["action"] == "truncate"
