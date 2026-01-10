"""
Health check tests for redactor plugins.

Story 4.29: Plugin Consistency and Completeness
"""

from __future__ import annotations

import pytest

from fapilog.plugins.redactors.field_mask import FieldMaskConfig, FieldMaskRedactor
from fapilog.plugins.redactors.regex_mask import RegexMaskConfig, RegexMaskRedactor
from fapilog.plugins.redactors.url_credentials import (
    UrlCredentialsConfig,
    UrlCredentialsRedactor,
)

pytestmark = pytest.mark.security


# FieldMaskRedactor tests
@pytest.mark.asyncio
async def test_field_mask_redactor_health_check_valid_config() -> None:
    """FieldMaskRedactor health check should return True with valid config."""
    redactor = FieldMaskRedactor(
        config=FieldMaskConfig(fields_to_mask=["password", "secret"])
    )
    result = await redactor.health_check()
    assert result is True


@pytest.mark.asyncio
async def test_field_mask_redactor_health_check_default_config() -> None:
    """FieldMaskRedactor health check should return True with default config."""
    redactor = FieldMaskRedactor()
    result = await redactor.health_check()
    assert result is True


@pytest.mark.asyncio
async def test_field_mask_redactor_has_health_check_method() -> None:
    """FieldMaskRedactor should have health_check method defined."""
    redactor = FieldMaskRedactor()
    assert hasattr(redactor, "health_check")
    assert callable(redactor.health_check)


# RegexMaskRedactor tests
@pytest.mark.asyncio
async def test_regex_mask_redactor_health_check_valid_patterns() -> None:
    """RegexMaskRedactor health check should return True with valid patterns."""
    redactor = RegexMaskRedactor(
        config=RegexMaskConfig(patterns=["^secret$", "password.*"])
    )
    result = await redactor.health_check()
    assert result is True


@pytest.mark.asyncio
async def test_regex_mask_redactor_health_check_empty_patterns() -> None:
    """RegexMaskRedactor health check should return True with empty patterns."""
    redactor = RegexMaskRedactor(config=RegexMaskConfig(patterns=[]))
    result = await redactor.health_check()
    assert result is True


@pytest.mark.asyncio
async def test_regex_mask_redactor_health_check_invalid_pattern() -> None:
    """RegexMaskRedactor health check should return False with invalid pattern."""
    # Invalid regex pattern (unclosed bracket)
    redactor = RegexMaskRedactor(config=RegexMaskConfig(patterns=["[invalid"]))
    result = await redactor.health_check()
    assert result is False


@pytest.mark.asyncio
async def test_regex_mask_redactor_health_check_mixed_patterns() -> None:
    """RegexMaskRedactor health check should return False if any pattern is invalid."""
    # Mix of valid and invalid patterns
    redactor = RegexMaskRedactor(
        config=RegexMaskConfig(patterns=["^valid$", "[invalid", "also_valid"])
    )
    result = await redactor.health_check()
    assert result is False


@pytest.mark.asyncio
async def test_regex_mask_redactor_has_health_check_method() -> None:
    """RegexMaskRedactor should have health_check method defined."""
    redactor = RegexMaskRedactor()
    assert hasattr(redactor, "health_check")
    assert callable(redactor.health_check)


# UrlCredentialsRedactor tests
@pytest.mark.asyncio
async def test_url_credentials_redactor_health_check() -> None:
    """UrlCredentialsRedactor health check should return True when healthy."""
    redactor = UrlCredentialsRedactor()
    result = await redactor.health_check()
    assert result is True


@pytest.mark.asyncio
async def test_url_credentials_redactor_health_check_with_config() -> None:
    """UrlCredentialsRedactor health check should return True with custom config."""
    redactor = UrlCredentialsRedactor(
        config=UrlCredentialsConfig(max_string_length=8192)
    )
    result = await redactor.health_check()
    assert result is True


@pytest.mark.asyncio
async def test_url_credentials_redactor_has_health_check_method() -> None:
    """UrlCredentialsRedactor should have health_check method defined."""
    redactor = UrlCredentialsRedactor()
    assert hasattr(redactor, "health_check")
    assert callable(redactor.health_check)
