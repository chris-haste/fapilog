from __future__ import annotations

import pytest
from pydantic import BaseModel

from fapilog.core.settings import (
    EnvFieldType,
    HttpSinkSettings,
    RoutingRule,
    Settings,
    SinkRoutingSettings,
    _apply_env_aliases,
)


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


def test_size_guard_env_aliases_parse_human_readable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAPILOG_SIZE_GUARD__MAX_BYTES", "1 MB")

    settings = Settings()

    assert settings.processor_config.size_guard.max_bytes == 1024 * 1024


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


def test_cloudwatch_env_aliases_parse_human_readable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAPILOG_CLOUDWATCH__BATCH_TIMEOUT_SECONDS", "10s")
    monkeypatch.setenv("FAPILOG_CLOUDWATCH__RETRY_BASE_DELAY", "2s")

    settings = Settings()
    cw = settings.sink_config.cloudwatch

    assert cw.batch_timeout_seconds == 10.0
    assert cw.retry_base_delay == 2.0


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


def test_loki_env_aliases_parse_human_readable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAPILOG_LOKI__TIMEOUT_SECONDS", "12s")
    monkeypatch.setenv("FAPILOG_LOKI__BATCH_TIMEOUT_SECONDS", "9s")
    monkeypatch.setenv("FAPILOG_LOKI__RETRY_BASE_DELAY", "1s")

    settings = Settings()
    loki = settings.sink_config.loki

    assert loki.timeout_seconds == 12.0
    assert loki.batch_timeout_seconds == 9.0
    assert loki.retry_base_delay == 1.0


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


def test_postgres_env_aliases_parse_human_readable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAPILOG_POSTGRES__POOL_ACQUIRE_TIMEOUT", "7s")
    monkeypatch.setenv("FAPILOG_POSTGRES__BATCH_TIMEOUT_SECONDS", "8s")
    monkeypatch.setenv("FAPILOG_POSTGRES__RETRY_BASE_DELAY", "3s")

    settings = Settings()
    pg = settings.sink_config.postgres

    assert pg.pool_acquire_timeout == 7.0
    assert pg.batch_timeout_seconds == 8.0
    assert pg.retry_base_delay == 3.0


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


# --- Tests for generic _apply_env_aliases function ---


class _TestModel(BaseModel):
    """Test model for _apply_env_aliases tests."""

    model_config = {"extra": "allow"}

    name: str = "default"
    count: int = 0
    enabled: bool = False
    rate: float = 1.0
    timeout: float = 5.0
    max_size: int = 1024
    tags: list[str] = []
    labels: dict[str, str] = {}
    action: str = "warn"
    rules: list[RoutingRule] = []


class TestApplyEnvAliasesString:
    """Tests for string type conversion."""

    def test_string_value_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_NAME", "custom-name")
        model = _TestModel()
        _apply_env_aliases(
            model,
            {"name": ("TEST_NAME", EnvFieldType.STRING)},
        )
        assert model.name == "custom-name"

    def test_missing_env_var_skipped(self) -> None:
        model = _TestModel()
        _apply_env_aliases(
            model,
            {"name": ("TEST_MISSING_VAR", EnvFieldType.STRING)},
        )
        assert model.name == "default"


class TestApplyEnvAliasesInt:
    """Tests for int type conversion."""

    def test_int_value_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_COUNT", "42")
        model = _TestModel()
        _apply_env_aliases(
            model,
            {"count": ("TEST_COUNT", EnvFieldType.INT)},
        )
        assert model.count == 42

    def test_invalid_int_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_COUNT", "not-an-int")
        model = _TestModel()
        _apply_env_aliases(
            model,
            {"count": ("TEST_COUNT", EnvFieldType.INT)},
        )
        assert model.count == 0  # Default unchanged


class TestApplyEnvAliasesBool:
    """Tests for bool type conversion."""

    @pytest.mark.parametrize(
        ("env_value", "expected"),
        [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("yes", True),
            ("on", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("0", False),
            ("no", False),
            ("off", False),
        ],
    )
    def test_bool_value_applied(
        self, monkeypatch: pytest.MonkeyPatch, env_value: str, expected: bool
    ) -> None:
        monkeypatch.setenv("TEST_ENABLED", env_value)
        model = _TestModel()
        _apply_env_aliases(
            model,
            {"enabled": ("TEST_ENABLED", EnvFieldType.BOOL)},
        )
        assert model.enabled is expected


class TestApplyEnvAliasesFloat:
    """Tests for float type conversion."""

    def test_float_value_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_RATE", "3.14")
        model = _TestModel()
        _apply_env_aliases(
            model,
            {"rate": ("TEST_RATE", EnvFieldType.FLOAT)},
        )
        assert model.rate == 3.14

    def test_invalid_float_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_RATE", "not-a-float")
        model = _TestModel()
        _apply_env_aliases(
            model,
            {"rate": ("TEST_RATE", EnvFieldType.FLOAT)},
        )
        assert model.rate == 1.0


class TestApplyEnvAliasesDuration:
    """Tests for duration type conversion."""

    @pytest.mark.parametrize(
        ("env_value", "expected"),
        [
            ("10", 10.0),
            ("10.5", 10.5),
            ("10s", 10.0),
            ("2m", 120.0),
            ("1h", 3600.0),
        ],
    )
    def test_duration_value_applied(
        self, monkeypatch: pytest.MonkeyPatch, env_value: str, expected: float
    ) -> None:
        monkeypatch.setenv("TEST_TIMEOUT", env_value)
        model = _TestModel()
        _apply_env_aliases(
            model,
            {"timeout": ("TEST_TIMEOUT", EnvFieldType.DURATION)},
        )
        assert model.timeout == expected

    def test_invalid_duration_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_TIMEOUT", "not-a-duration")
        model = _TestModel()
        _apply_env_aliases(
            model,
            {"timeout": ("TEST_TIMEOUT", EnvFieldType.DURATION)},
        )
        assert model.timeout == 5.0


class TestApplyEnvAliasesSize:
    """Tests for size type conversion."""

    @pytest.mark.parametrize(
        ("env_value", "expected"),
        [
            ("1024", 1024),
            ("1 KB", 1024),
            ("1 MB", 1024 * 1024),
            ("500 KB", 500 * 1024),
        ],
    )
    def test_size_value_applied(
        self, monkeypatch: pytest.MonkeyPatch, env_value: str, expected: int
    ) -> None:
        monkeypatch.setenv("TEST_SIZE", env_value)
        model = _TestModel()
        _apply_env_aliases(
            model,
            {"max_size": ("TEST_SIZE", EnvFieldType.SIZE)},
        )
        assert model.max_size == expected

    def test_invalid_size_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_SIZE", "not-a-size")
        model = _TestModel()
        _apply_env_aliases(
            model,
            {"max_size": ("TEST_SIZE", EnvFieldType.SIZE)},
        )
        assert model.max_size == 1024


class TestApplyEnvAliasesList:
    """Tests for list type conversion."""

    def test_list_json_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_TAGS", '["a", "b", "c"]')
        model = _TestModel()
        _apply_env_aliases(
            model,
            {"tags": ("TEST_TAGS", EnvFieldType.LIST)},
        )
        assert model.tags == ["a", "b", "c"]

    def test_list_csv_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_TAGS", "a, b, c")
        model = _TestModel()
        _apply_env_aliases(
            model,
            {"tags": ("TEST_TAGS", EnvFieldType.LIST)},
        )
        assert model.tags == ["a", "b", "c"]

    def test_empty_list_from_whitespace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_TAGS", "  ")
        model = _TestModel()
        _apply_env_aliases(
            model,
            {"tags": ("TEST_TAGS", EnvFieldType.LIST)},
        )
        assert model.tags == []


class TestApplyEnvAliasesDict:
    """Tests for dict type conversion."""

    def test_dict_json_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_LABELS", '{"env": "prod", "app": "test"}')
        model = _TestModel()
        _apply_env_aliases(
            model,
            {"labels": ("TEST_LABELS", EnvFieldType.DICT)},
        )
        assert model.labels == {"env": "prod", "app": "test"}

    def test_invalid_dict_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_LABELS", "{not-json")
        model = _TestModel()
        _apply_env_aliases(
            model,
            {"labels": ("TEST_LABELS", EnvFieldType.DICT)},
        )
        assert model.labels == {}

    def test_non_dict_json_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_LABELS", '["not", "a", "dict"]')
        model = _TestModel()
        _apply_env_aliases(
            model,
            {"labels": ("TEST_LABELS", EnvFieldType.DICT)},
        )
        assert model.labels == {}


class TestApplyEnvAliasesEnum:
    """Tests for enum type conversion (constrained choices)."""

    def test_enum_value_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_ACTION", "drop")
        model = _TestModel()
        _apply_env_aliases(
            model,
            {
                "action": (
                    "TEST_ACTION",
                    EnvFieldType.ENUM,
                    {"truncate", "drop", "warn"},
                )
            },
        )
        assert model.action == "drop"

    def test_invalid_enum_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_ACTION", "invalid-action")
        model = _TestModel()
        _apply_env_aliases(
            model,
            {
                "action": (
                    "TEST_ACTION",
                    EnvFieldType.ENUM,
                    {"truncate", "drop", "warn"},
                )
            },
        )
        assert model.action == "warn"

    def test_enum_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_ACTION", "DROP")
        model = _TestModel()
        _apply_env_aliases(
            model,
            {
                "action": (
                    "TEST_ACTION",
                    EnvFieldType.ENUM,
                    {"truncate", "drop", "warn"},
                )
            },
        )
        assert model.action == "drop"


class TestApplyEnvAliasesRoutingRules:
    """Tests for routing_rules type conversion."""

    def test_routing_rules_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        rules_json = '[{"levels": ["ERROR"], "sinks": ["cloudwatch"]}]'
        monkeypatch.setenv("TEST_RULES", rules_json)
        model = _TestModel()
        _apply_env_aliases(
            model,
            {"rules": ("TEST_RULES", EnvFieldType.ROUTING_RULES)},
        )
        assert len(model.rules) == 1
        assert model.rules[0].levels == ["ERROR"]
        assert model.rules[0].sinks == ["cloudwatch"]

    def test_invalid_routing_rules_skipped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TEST_RULES", "{not-json")
        model = _TestModel()
        _apply_env_aliases(
            model,
            {"rules": ("TEST_RULES", EnvFieldType.ROUTING_RULES)},
        )
        assert model.rules == []

    def test_non_list_routing_rules_skipped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TEST_RULES", '{"not": "a list"}')
        model = _TestModel()
        _apply_env_aliases(
            model,
            {"rules": ("TEST_RULES", EnvFieldType.ROUTING_RULES)},
        )
        assert model.rules == []


class TestApplyEnvAliasesMultipleFields:
    """Tests for applying multiple fields at once."""

    def test_multiple_fields_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_NAME", "multi-test")
        monkeypatch.setenv("TEST_COUNT", "100")
        monkeypatch.setenv("TEST_ENABLED", "true")

        model = _TestModel()
        _apply_env_aliases(
            model,
            {
                "name": ("TEST_NAME", EnvFieldType.STRING),
                "count": ("TEST_COUNT", EnvFieldType.INT),
                "enabled": ("TEST_ENABLED", EnvFieldType.BOOL),
            },
        )

        assert model.name == "multi-test"
        assert model.count == 100
        assert model.enabled is True
