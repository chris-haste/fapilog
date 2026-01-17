"""Tests for config_builders module extracted from __init__.py (Story 5.25)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from fapilog.core.settings import Settings


class TestModuleImports:
    """Verify all expected functions can be imported from config_builders."""

    def test_sink_configs_importable(self) -> None:
        """_sink_configs can be imported from config_builders."""
        from fapilog.core.config_builders import _sink_configs

        assert callable(_sink_configs)

    def test_enricher_configs_importable(self) -> None:
        """_enricher_configs can be imported from config_builders."""
        from fapilog.core.config_builders import _enricher_configs

        assert callable(_enricher_configs)

    def test_redactor_configs_importable(self) -> None:
        """_redactor_configs can be imported from config_builders."""
        from fapilog.core.config_builders import _redactor_configs

        assert callable(_redactor_configs)

    def test_filter_configs_importable(self) -> None:
        """_filter_configs can be imported from config_builders."""
        from fapilog.core.config_builders import _filter_configs

        assert callable(_filter_configs)

    def test_processor_configs_importable(self) -> None:
        """_processor_configs can be imported from config_builders."""
        from fapilog.core.config_builders import _processor_configs

        assert callable(_processor_configs)

    def test_default_sink_names_importable(self) -> None:
        """_default_sink_names can be imported from config_builders."""
        from fapilog.core.config_builders import _default_sink_names

        assert callable(_default_sink_names)

    def test_default_env_sink_cfg_importable(self) -> None:
        """_default_env_sink_cfg can be imported from config_builders."""
        from fapilog.core.config_builders import _default_env_sink_cfg

        assert callable(_default_env_sink_cfg)

    def test_build_pipeline_importable(self) -> None:
        """_build_pipeline can be imported from config_builders."""
        from fapilog.core.config_builders import _build_pipeline

        assert callable(_build_pipeline)


class TestSinkConfigs:
    """Test _sink_configs returns expected structure."""

    def test_returns_dict_with_expected_sink_keys(self) -> None:
        """_sink_configs returns dict containing all standard sink names."""
        from fapilog.core.config_builders import _sink_configs

        settings = Settings()
        result = _sink_configs(settings)

        expected_keys = {
            "stdout_json",
            "stdout_pretty",
            "rotating_file",
            "http",
            "webhook",
            "loki",
            "cloudwatch",
            "postgres",
            "sealed",
        }
        assert expected_keys.issubset(result.keys())

    def test_rotating_file_has_config_object(self) -> None:
        """rotating_file sink config contains a config object."""
        from fapilog.core.config_builders import _sink_configs

        settings = Settings()
        result = _sink_configs(settings)

        assert "config" in result["rotating_file"]

    def test_http_sink_has_config_object(self) -> None:
        """http sink config contains a config object."""
        from fapilog.core.config_builders import _sink_configs

        settings = Settings()
        result = _sink_configs(settings)

        assert "config" in result["http"]


class TestEnricherConfigs:
    """Test _enricher_configs returns expected structure."""

    def test_returns_dict_with_expected_enricher_keys(self) -> None:
        """_enricher_configs returns dict with standard enricher names."""
        from fapilog.core.config_builders import _enricher_configs

        settings = Settings()
        result = _enricher_configs(settings)

        assert "runtime_info" in result
        assert "context_vars" in result
        assert "integrity" in result


class TestRedactorConfigs:
    """Test _redactor_configs returns expected structure."""

    def test_returns_dict_with_expected_redactor_keys(self) -> None:
        """_redactor_configs returns dict with standard redactor names."""
        from fapilog.core.config_builders import _redactor_configs

        settings = Settings()
        result = _redactor_configs(settings)

        assert "field_mask" in result
        assert "regex_mask" in result
        assert "url_credentials" in result

    def test_field_mask_has_config_object(self) -> None:
        """field_mask redactor config contains a config object."""
        from fapilog.core.config_builders import _redactor_configs

        settings = Settings()
        result = _redactor_configs(settings)

        assert "config" in result["field_mask"]


class TestFilterConfigs:
    """Test _filter_configs returns expected structure."""

    def test_returns_dict_with_expected_filter_keys(self) -> None:
        """_filter_configs returns dict with standard filter names."""
        from fapilog.core.config_builders import _filter_configs

        settings = Settings()
        result = _filter_configs(settings)

        expected_keys = {
            "level",
            "sampling",
            "rate_limit",
            "adaptive_sampling",
            "trace_sampling",
            "first_occurrence",
        }
        assert expected_keys.issubset(result.keys())


class TestProcessorConfigs:
    """Test _processor_configs returns expected structure."""

    def test_returns_dict_with_expected_processor_keys(self) -> None:
        """_processor_configs returns dict with standard processor names."""
        from fapilog.core.config_builders import _processor_configs

        settings = Settings()
        result = _processor_configs(settings)

        assert "zero_copy" in result
        assert "size_guard" in result

    def test_size_guard_has_config_object(self) -> None:
        """size_guard processor config contains a config object."""
        from fapilog.core.config_builders import _processor_configs

        settings = Settings()
        result = _processor_configs(settings)

        assert "config" in result["size_guard"]

    def test_metrics_passed_to_size_guard(self) -> None:
        """Metrics collector is passed to size_guard config when provided."""
        from fapilog.core.config_builders import _processor_configs
        from fapilog.metrics.metrics import MetricsCollector

        settings = Settings()
        metrics = MetricsCollector(enabled=True)
        result = _processor_configs(settings, metrics)

        assert result["size_guard"].get("metrics") is metrics


class TestDefaultSinkNames:
    """Test _default_sink_names returns correct defaults."""

    def test_returns_stdout_json_by_default(self) -> None:
        """Without HTTP endpoint or file directory, returns stdout_json."""
        from fapilog.core.config_builders import _default_sink_names

        settings = Settings()
        result = _default_sink_names(settings)

        assert result == ["stdout_json"]

    def test_returns_http_when_endpoint_configured(self) -> None:
        """When HTTP endpoint is set, returns http sink."""
        from fapilog.core.config_builders import _default_sink_names

        settings = Settings(http={"endpoint": "https://example.com/logs"})
        result = _default_sink_names(settings)

        assert result == ["http"]

    def test_returns_rotating_file_when_env_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When FAPILOG_FILE__DIRECTORY env is set, returns rotating_file."""
        from fapilog.core.config_builders import _default_sink_names

        monkeypatch.setenv("FAPILOG_FILE__DIRECTORY", "/tmp/logs")
        settings = Settings()
        result = _default_sink_names(settings)

        assert result == ["rotating_file"]


class TestDefaultEnvSinkCfg:
    """Test _default_env_sink_cfg returns environment-based config."""

    def test_rotating_file_returns_config_dict(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """rotating_file returns dict with config key."""
        from fapilog.core.config_builders import _default_env_sink_cfg

        monkeypatch.setenv("FAPILOG_FILE__DIRECTORY", "/tmp/logs")
        result = _default_env_sink_cfg("rotating_file")

        assert "config" in result

    def test_unknown_sink_returns_empty_dict(self) -> None:
        """Unknown sink name returns empty dict."""
        from fapilog.core.config_builders import _default_env_sink_cfg

        result = _default_env_sink_cfg("unknown_sink")

        assert result == {}

    def test_rotating_file_respects_env_vars(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """rotating_file config respects environment variables."""
        from fapilog.core.config_builders import _default_env_sink_cfg

        monkeypatch.setenv("FAPILOG_FILE__DIRECTORY", "/custom/path")
        monkeypatch.setenv("FAPILOG_FILE__FILENAME_PREFIX", "myapp")
        result = _default_env_sink_cfg("rotating_file")

        config = result["config"]
        assert str(config.directory) == "/custom/path"
        assert config.filename_prefix == "myapp"


class TestBuildPipeline:
    """Test _build_pipeline constructs correct plugin lists."""

    def test_accepts_load_plugins_callable(self) -> None:
        """_build_pipeline accepts load_plugins as a callable parameter."""
        from fapilog.core.config_builders import _build_pipeline

        settings = Settings()
        mock_loader: Any = MagicMock(return_value=[])

        # Should not raise - accepts load_plugins parameter
        result = _build_pipeline(settings, mock_loader)

        assert isinstance(result, tuple)
        assert (
            len(result) == 6
        )  # sinks, enrichers, redactors, processors, filters, metrics

    def test_calls_load_plugins_for_sinks(self) -> None:
        """_build_pipeline calls load_plugins for sinks."""
        from fapilog.core.config_builders import _build_pipeline

        settings = Settings()
        mock_loader: Any = MagicMock(return_value=[])

        _build_pipeline(settings, mock_loader)

        # Should have called load_plugins with "fapilog.sinks" exactly once
        calls = [c for c in mock_loader.call_args_list if c[0][0] == "fapilog.sinks"]
        assert len(calls) == 1

    def test_returns_fallback_sink_when_none_loaded(self) -> None:
        """_build_pipeline returns StdoutJsonSink when no sinks loaded."""
        from fapilog.core.config_builders import _build_pipeline
        from fapilog.plugins.sinks.stdout_json import StdoutJsonSink

        settings = Settings()
        mock_loader: Any = MagicMock(return_value=[])

        sinks, _, _, _, _, _ = _build_pipeline(settings, mock_loader)

        assert len(sinks) == 1
        assert isinstance(sinks[0], StdoutJsonSink)

    def test_returns_metrics_when_enabled(self) -> None:
        """_build_pipeline returns MetricsCollector when metrics enabled."""
        from fapilog.core.config_builders import _build_pipeline
        from fapilog.metrics.metrics import MetricsCollector

        settings = Settings(core={"enable_metrics": True})
        mock_loader: Any = MagicMock(return_value=[])

        _, _, _, _, _, metrics = _build_pipeline(settings, mock_loader)

        assert isinstance(metrics, MetricsCollector)

    def test_returns_none_metrics_when_disabled(self) -> None:
        """_build_pipeline returns None for metrics when disabled."""
        from fapilog.core.config_builders import _build_pipeline

        settings = Settings(core={"enable_metrics": False})
        mock_loader: Any = MagicMock(return_value=[])

        _, _, _, _, _, metrics = _build_pipeline(settings, mock_loader)

        assert metrics is None
