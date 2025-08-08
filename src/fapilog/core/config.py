"""
Async configuration loading and validation for Fapilog v3.

Provides typed, async-first loading from environment variables using
Pydantic v2 settings, with optional overrides and schema versioning.
"""

from __future__ import annotations

import os
from typing import Any, Mapping, MutableMapping

from pydantic import ValidationError as PydanticValidationError

from .errors import (
    ConfigurationError,
    ErrorCategory,
    ErrorSeverity,
    create_error_context,
)
from .settings import LATEST_CONFIG_SCHEMA_VERSION, Settings


def _deep_update_dict(
    base: dict[str, Any], updates: Mapping[str, Any]
) -> dict[str, Any]:
    """Recursively update a dictionary and return it.

    Values in `updates` replace or merge into `base` depending on type.
    Lists and non-dict values are replaced.
    """
    for key, value in updates.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, Mapping):
            base[key] = _deep_update_dict(base[key], value)
        else:
            base[key] = value
    return base


async def load_settings(
    *,
    env: Mapping[str, str] | None = None,
    overrides: MutableMapping[str, Any] | None = None,
) -> Settings:
    """Load settings asynchronously with optional env and runtime overrides.

    Args:
        env: Optional mapping for environment variables
            (defaults to os.environ)
        overrides: Optional dict of field overrides applied after env loading.

    Returns:
        Fully validated `Settings` instance.

    Raises:
        ConfigurationError: On validation errors or schema mismatch.
    """

    # Build instantiation kwargs
    init_kwargs: dict[str, Any] = {}

    if env is not None:
        # pydantic-settings reads from os.environ; allow injection for tests.
        # Use a temporary environment to isolate this operation.
        sentinel_backup = dict(os.environ)
        try:
            os.environ.clear()
            os.environ.update(env)
            settings = Settings(**init_kwargs)
        finally:
            os.environ.clear()
            os.environ.update(sentinel_backup)
    else:
        settings = Settings(**init_kwargs)

    # Apply runtime overrides (dot-path style not supported; pass nested dicts)
    if overrides:
        # Build a plain dict of current settings, apply deep overrides, then
        # re-validate to ensure nested models are constructed properly.
        data = settings.model_dump()
        data = _deep_update_dict(data, overrides)
        settings = Settings.model_validate(data)

    # Schema version check
    if settings.schema_version != LATEST_CONFIG_SCHEMA_VERSION:
        context = create_error_context(
            ErrorCategory.CONFIG,
            ErrorSeverity.HIGH,
        )
        raise ConfigurationError(
            (
                "Unsupported settings schema_version="
                f"{settings.schema_version}; expected "
                f"{LATEST_CONFIG_SCHEMA_VERSION}"
            ),
            error_context=context,
        )

    # Async validation (I/O capable checks)
    try:
        await settings.validate_async()
    except PydanticValidationError as e:
        context = create_error_context(
            ErrorCategory.CONFIG,
            ErrorSeverity.HIGH,
        )
        raise ConfigurationError(
            "Pydantic validation failed", error_context=context, cause=e
        ) from e
    except FileNotFoundError as e:
        context = create_error_context(
            ErrorCategory.CONFIG,
            ErrorSeverity.HIGH,
        )
        raise ConfigurationError(str(e), error_context=context, cause=e) from e
    except Exception as e:  # Defensive barrier to surface config issues
        context = create_error_context(
            ErrorCategory.CONFIG,
            ErrorSeverity.HIGH,
        )
        raise ConfigurationError(
            "Async settings validation failed",
            error_context=context,
            cause=e,
        ) from e

    return settings
