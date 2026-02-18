"""Tests for LoggerBuilder.with_adaptive() method (Story 10.57 AC2)."""

from fapilog.builder import LoggerBuilder


class TestWithAdaptive:
    """Tests for with_adaptive() builder method."""

    def test_with_adaptive_sets_enabled(self) -> None:
        """with_adaptive() sets adaptive.enabled to True by default."""
        builder = LoggerBuilder()
        builder.with_adaptive()
        assert builder._config["adaptive"]["enabled"] is True

    def test_with_adaptive_disabled(self) -> None:
        """with_adaptive(enabled=False) sets adaptive.enabled to False."""
        builder = LoggerBuilder()
        builder.with_adaptive(enabled=False)
        assert builder._config["adaptive"]["enabled"] is False

    def test_with_adaptive_sets_max_workers(self) -> None:
        """with_adaptive(max_workers=6) sets adaptive.max_workers."""
        builder = LoggerBuilder()
        builder.with_adaptive(max_workers=6)
        assert builder._config["adaptive"]["max_workers"] == 6

    def test_with_adaptive_sets_batch_sizing(self) -> None:
        """with_adaptive(batch_sizing=True) sets adaptive.batch_sizing."""
        builder = LoggerBuilder()
        builder.with_adaptive(batch_sizing=True)
        assert builder._config["adaptive"]["batch_sizing"] is True

    def test_with_adaptive_sets_check_interval(self) -> None:
        """with_adaptive(check_interval_seconds=0.5) sets check interval."""
        builder = LoggerBuilder()
        builder.with_adaptive(check_interval_seconds=0.5)
        assert builder._config["adaptive"]["check_interval_seconds"] == 0.5

    def test_with_adaptive_sets_cooldown(self) -> None:
        """with_adaptive(cooldown_seconds=3.0) sets cooldown."""
        builder = LoggerBuilder()
        builder.with_adaptive(cooldown_seconds=3.0)
        assert builder._config["adaptive"]["cooldown_seconds"] == 3.0

    def test_with_adaptive_sets_circuit_pressure_boost(self) -> None:
        """with_adaptive(circuit_pressure_boost=0.15) sets boost."""
        builder = LoggerBuilder()
        builder.with_adaptive(circuit_pressure_boost=0.15)
        assert builder._config["adaptive"]["circuit_pressure_boost"] == 0.15

    def test_with_adaptive_returns_self(self) -> None:
        """with_adaptive() returns self for method chaining."""
        builder = LoggerBuilder()
        result = builder.with_adaptive()
        assert result is builder

    def test_with_adaptive_none_params_omitted(self) -> None:
        """with_adaptive() with defaults only sets enabled."""
        builder = LoggerBuilder()
        builder.with_adaptive()
        adaptive = builder._config["adaptive"]
        assert adaptive == {"enabled": True}

    def test_with_adaptive_chaining_with_circuit_breaker(self) -> None:
        """with_adaptive() chains with with_circuit_breaker()."""
        builder = LoggerBuilder()
        result = builder.with_adaptive(
            max_workers=6, batch_sizing=True
        ).with_circuit_breaker(enabled=True, fallback_sink="rotating_file")
        assert result is builder
        assert builder._config["adaptive"]["max_workers"] == 6
        assert builder._config["core"]["sink_circuit_breaker_enabled"] is True

    def test_with_adaptive_merges_on_repeated_calls(self) -> None:
        """Calling with_adaptive() twice merges values."""
        builder = LoggerBuilder()
        builder.with_adaptive(max_workers=4)
        builder.with_adaptive(batch_sizing=True)
        adaptive = builder._config["adaptive"]
        assert adaptive["max_workers"] == 4
        assert adaptive["batch_sizing"] is True
        assert adaptive["enabled"] is True

    def test_with_adaptive_with_preset_overrides(self) -> None:
        """with_adaptive() overrides preset adaptive settings."""
        builder = LoggerBuilder()
        builder.with_preset("adaptive").with_adaptive(max_workers=4)
        # Builder config should have the override
        assert builder._config["adaptive"]["max_workers"] == 4

    # Story 1.51: Per-actuator toggles

    def test_with_adaptive_filter_tightening_param(self) -> None:
        """with_adaptive(filter_tightening=False) sets the toggle."""
        builder = LoggerBuilder()
        builder.with_adaptive(filter_tightening=False)
        assert builder._config["adaptive"]["filter_tightening"] is False

    def test_with_adaptive_worker_scaling_param(self) -> None:
        """with_adaptive(worker_scaling=False) sets the toggle."""
        builder = LoggerBuilder()
        builder.with_adaptive(worker_scaling=False)
        assert builder._config["adaptive"]["worker_scaling"] is False

    def test_with_adaptive_toggle_none_omitted(self) -> None:
        """Toggle params default to None and are omitted from config."""
        builder = LoggerBuilder()
        builder.with_adaptive()
        adaptive = builder._config["adaptive"]
        assert "filter_tightening" not in adaptive
        assert "worker_scaling" not in adaptive
        assert "queue_growth" not in adaptive
