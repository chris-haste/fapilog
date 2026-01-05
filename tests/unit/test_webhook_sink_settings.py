from __future__ import annotations

from fapilog import Settings, _sink_configs
from fapilog.core.settings import WebhookSettings


def test_webhook_settings_defaults() -> None:
    cfg = WebhookSettings()
    assert cfg.batch_size == 1
    assert cfg.batch_timeout_seconds == 5.0


def test_webhook_settings_to_config_carries_batch_fields() -> None:
    settings = Settings(
        sink_config={
            "webhook": {
                "endpoint": "https://hooks.example.com",
                "batch_size": 5,
                "batch_timeout_seconds": 1.5,
            }
        }
    )

    cfgs = _sink_configs(settings)
    webhook_cfg = cfgs["webhook"]["config"]

    assert webhook_cfg.batch_size == 5
    assert webhook_cfg.batch_timeout_seconds == 1.5
