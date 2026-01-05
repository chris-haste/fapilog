from __future__ import annotations

from fapilog import Settings, _sink_configs
from fapilog.core.settings import HttpSinkSettings


def test_http_sink_settings_defaults() -> None:
    cfg = HttpSinkSettings()
    assert cfg.batch_size == 1
    assert cfg.batch_timeout_seconds == 5.0
    assert cfg.batch_format == "array"
    assert cfg.batch_wrapper_key == "logs"


def test_http_sink_config_from_settings_includes_batch_fields() -> None:
    settings = Settings(
        http={
            "endpoint": "https://logs.example.com",
            "batch_size": 10,
            "batch_timeout_seconds": 2.5,
            "batch_format": "ndjson",
            "batch_wrapper_key": "events",
        }
    )

    cfgs = _sink_configs(settings)
    http_cfg = cfgs["http"]["config"]

    assert http_cfg.batch_size == 10
    assert http_cfg.batch_timeout_seconds == 2.5
    assert http_cfg.batch_format.value == "ndjson"
    assert http_cfg.batch_wrapper_key == "events"
