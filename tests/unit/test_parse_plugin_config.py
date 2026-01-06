from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from fapilog.plugins.utils import parse_plugin_config


class SampleConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)

    value: int = 10
    name: str = "default"


class StrictConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rate: float = Field(default=1.0, ge=0.0, le=1.0)


def test_parse_config_object_returned_as_is() -> None:
    cfg = SampleConfig(value=20)
    result = parse_plugin_config(SampleConfig, cfg)
    assert result is cfg


def test_parse_config_from_dict() -> None:
    result = parse_plugin_config(SampleConfig, {"value": 30, "name": "test"})
    assert result.value == 30
    assert result.name == "test"


def test_parse_config_with_nested_config_key() -> None:
    result = parse_plugin_config(SampleConfig, {"config": {"value": 40}})
    assert result.value == 40
    assert result.name == "default"


def test_parse_config_from_kwargs() -> None:
    result = parse_plugin_config(SampleConfig, None, value=50)
    assert result.value == 50
    assert result.name == "default"


def test_parse_config_defaults_when_empty() -> None:
    result = parse_plugin_config(SampleConfig, None)
    assert result.value == 10
    assert result.name == "default"


def test_parse_config_nested_kwargs_unwraps() -> None:
    result = parse_plugin_config(SampleConfig, None, config={"value": 60})
    assert result.value == 60


def test_parse_config_invalid_type_raises_type_error() -> None:
    with pytest.raises(TypeError, match="expected SampleConfig"):
        parse_plugin_config(SampleConfig, "invalid")  # type: ignore[arg-type]


def test_pydantic_type_coercion() -> None:
    result = parse_plugin_config(SampleConfig, {"value": "42"})
    assert result.value == 42
    assert isinstance(result.value, int)


def test_pydantic_validation_and_bounds() -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        parse_plugin_config(StrictConfig, {"rate": -0.1})
    with pytest.raises(ValidationError, match="less than or equal to 1"):
        parse_plugin_config(StrictConfig, {"rate": 1.1})


def test_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        parse_plugin_config(SampleConfig, {"value": 1, "other": "oops"})


def test_invalid_value_error_message_is_clear() -> None:
    with pytest.raises(ValidationError, match="Input should be a valid integer"):
        parse_plugin_config(SampleConfig, {"value": "not-a-number"})


def test_config_objects_are_immutable() -> None:
    cfg = parse_plugin_config(SampleConfig, {"value": 5})
    with pytest.raises(ValidationError):
        cfg.value = 10  # type: ignore[misc]


def test_loader_compatibility_unwraps_config_key() -> None:
    result = parse_plugin_config(
        SampleConfig, {"config": {"value": 100, "name": "loader"}}
    )
    assert result.value == 100
    assert result.name == "loader"
