from __future__ import annotations

import pytest

from fapilog.core.settings import HttpSinkSettings, Settings, SinkRoutingSettings


def test_sink_routing_fallback_coercion() -> None:
    assert SinkRoutingSettings(fallback_sinks=None).fallback_sinks == []
    assert SinkRoutingSettings(fallback_sinks=["a", 2]).fallback_sinks == ["a", "2"]
    assert SinkRoutingSettings(fallback_sinks='["a", "b"]').fallback_sinks == [
        "a",
        "b",
    ]
    assert SinkRoutingSettings(fallback_sinks="a, b ,").fallback_sinks == ["a", "b"]
    assert SinkRoutingSettings(fallback_sinks={"a": 1}).fallback_sinks == []


def test_http_headers_json_parsing_and_resolution() -> None:
    assert HttpSinkSettings(headers_json=" ").headers_json is None

    with pytest.raises(ValueError, match="headers_json must decode to a JSON object"):
        HttpSinkSettings(headers_json='["bad"]')

    with pytest.raises(ValueError, match="Invalid headers_json"):
        HttpSinkSettings(headers_json="{invalid-json")

    settings = HttpSinkSettings(headers={"A": "1"}, headers_json='{"B": "2"}')
    assert settings.resolved_headers() == {"A": "1"}

    settings = HttpSinkSettings(headers_json='{"B": "2"}')
    assert settings.resolved_headers() == {"B": "2"}


def test_parse_env_list_json_and_csv() -> None:
    assert Settings._parse_env_list("  ") == []
    assert Settings._parse_env_list('["a", "b"]') == ["a", "b"]
    assert Settings._parse_env_list("a, b,") == ["a", "b"]


def test_size_guard_env_aliases_apply(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAPILOG_SIZE_GUARD__ACTION", "drop")
    monkeypatch.setenv("FAPILOG_SIZE_GUARD__MAX_BYTES", "1024")
    monkeypatch.setenv("FAPILOG_SIZE_GUARD__PRESERVE_FIELDS", '["keep"]')

    settings = Settings()
    sg = settings.processor_config.size_guard

    assert sg.action == "drop"
    assert sg.max_bytes == 1024
    assert sg.preserve_fields == ["keep"]


def test_size_guard_env_aliases_ignore_invalid_max_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAPILOG_SIZE_GUARD__MAX_BYTES", "not-an-int")

    settings = Settings()

    assert settings.processor_config.size_guard.max_bytes == 256000


def test_cloudwatch_env_aliases_parse_and_ignore_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAPILOG_CLOUDWATCH__LOG_GROUP_NAME", "/env/group")
    monkeypatch.setenv("FAPILOG_CLOUDWATCH__BATCH_SIZE", "5")
    monkeypatch.setenv("FAPILOG_CLOUDWATCH__RETRY_BASE_DELAY", "0.25")
    monkeypatch.setenv("FAPILOG_CLOUDWATCH__CREATE_LOG_GROUP", "false")
    monkeypatch.setenv("FAPILOG_CLOUDWATCH__CIRCUIT_BREAKER_THRESHOLD", "12")
    monkeypatch.setenv("FAPILOG_CLOUDWATCH__BATCH_TIMEOUT_SECONDS", "bad")

    settings = Settings()
    cw = settings.sink_config.cloudwatch

    assert cw.log_group_name == "/env/group"
    assert cw.batch_size == 5
    assert cw.retry_base_delay == 0.25
    assert cw.create_log_group is False
    assert cw.circuit_breaker_threshold == 12
    assert cw.batch_timeout_seconds == 5.0


def test_cloudwatch_env_aliases_ignore_invalid_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAPILOG_CLOUDWATCH__CIRCUIT_BREAKER_THRESHOLD", "bad")

    settings = Settings()
    cw = settings.sink_config.cloudwatch

    assert cw.circuit_breaker_threshold == 5


def test_loki_env_aliases_parse_and_ignore_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAPILOG_LOKI__URL", "http://env-loki")
    monkeypatch.setenv("FAPILOG_LOKI__BATCH_SIZE", "bad")
    monkeypatch.setenv("FAPILOG_LOKI__CIRCUIT_BREAKER_ENABLED", "true")
    monkeypatch.setenv("FAPILOG_LOKI__CIRCUIT_BREAKER_THRESHOLD", "7")
    monkeypatch.setenv("FAPILOG_LOKI__LABELS", '{"env": "dev"}')
    monkeypatch.setenv("FAPILOG_LOKI__LABEL_KEYS", '["level", "service"]')

    settings = Settings()
    loki = settings.sink_config.loki

    assert loki.url == "http://env-loki"
    assert loki.batch_size == 100
    assert loki.circuit_breaker_enabled is True
    assert loki.circuit_breaker_threshold == 7
    assert loki.labels == {"env": "dev"}
    assert loki.label_keys == ["level", "service"]


def test_loki_env_aliases_parse_timeout_and_ignore_invalid_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAPILOG_LOKI__TIMEOUT_SECONDS", "9.5")
    monkeypatch.setenv("FAPILOG_LOKI__CIRCUIT_BREAKER_THRESHOLD", "bad")

    settings = Settings()
    loki = settings.sink_config.loki

    assert loki.timeout_seconds == 9.5
    assert loki.circuit_breaker_threshold == 5


def test_postgres_env_aliases_parse_and_ignore_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAPILOG_POSTGRES__PORT", "15432")
    monkeypatch.setenv("FAPILOG_POSTGRES__POOL_ACQUIRE_TIMEOUT", "2.5")
    monkeypatch.setenv("FAPILOG_POSTGRES__MAX_RETRIES", "bad")
    monkeypatch.setenv("FAPILOG_POSTGRES__CREATE_TABLE", "false")
    monkeypatch.setenv("FAPILOG_POSTGRES__EXTRACT_FIELDS", '["level", "message"]')

    settings = Settings()
    pg = settings.sink_config.postgres

    assert pg.port == 15432
    assert pg.pool_acquire_timeout == 2.5
    assert pg.max_retries == 3
    assert pg.create_table is False
    assert pg.extract_fields == ["level", "message"]


def test_sink_routing_env_aliases_ignore_invalid_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings()

    def _fake_getenv(key: str, default: str | None = None) -> str | None:
        if key == "FAPILOG_SINK_ROUTING__ENABLED":
            return "true"
        if key == "FAPILOG_SINK_ROUTING__RULES":
            return "{not-json"
        return default

    monkeypatch.setattr("fapilog.core.settings.os.getenv", _fake_getenv)
    settings._apply_sink_routing_env_aliases()

    assert settings.sink_routing.enabled is True
    assert settings.sink_routing.rules == []
