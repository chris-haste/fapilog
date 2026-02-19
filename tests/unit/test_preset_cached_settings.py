"""Tests for Story 1.57: Preset settings flow into cached fields.

Ensures _common_init reads from the caller-provided Settings object
(resolved from presets) instead of constructing a fresh Settings().
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from fapilog import get_logger
from fapilog.core.logger import SyncLoggerFacade


class TestPresetSinkConcurrency:
    """AC1: Preset sink_concurrency is honored."""

    def test_production_preset_sink_concurrency(self):
        """get_logger(preset='production') caches sink_concurrency=8."""
        logger = get_logger(name="test-sc", preset="production", reuse=False)
        assert logger._cached_sink_concurrency == 8

    def test_dev_preset_sink_concurrency_is_default(self):
        """Dev preset does not override sink_concurrency (stays at 1)."""
        logger = get_logger(name="test-sc-dev", preset="dev", reuse=False)
        assert logger._cached_sink_concurrency == 1


class TestPresetAdaptiveEnabled:
    """AC2: Preset adaptive.enabled is honored."""

    def test_production_preset_adaptive_enabled(self):
        """get_logger(preset='production') caches adaptive_enabled=True."""
        logger = get_logger(name="test-ae", preset="production", reuse=False)
        assert logger._cached_adaptive_enabled is True

    def test_production_preset_adaptive_settings_populated(self):
        """get_logger(preset='production') populates adaptive_settings with max_workers=4."""
        logger = get_logger(name="test-as", preset="production", reuse=False)
        assert logger._cached_adaptive_settings is not None  # noqa: WA003
        assert logger._cached_adaptive_settings.max_workers == 4


class TestAllCachedFieldsFromSettings:
    """AC3: All cached fields read from passed-in settings."""

    def test_strict_envelope_mode_from_preset(self):
        """Cached strict_envelope_mode reads from resolved settings."""
        from fapilog import Settings

        settings = Settings(core={"strict_envelope_mode": True})
        logger = get_logger(name="test-sem", settings=settings, reuse=False)
        assert logger._cached_strict_envelope_mode is True


class TestBackwardCompatibility:
    """AC4: Direct construction without settings falls back to Settings()."""

    def test_sync_facade_without_settings_uses_defaults(self):
        """SyncLoggerFacade() without settings param still works."""
        sink = MagicMock()
        facade = SyncLoggerFacade(
            name="test-bc",
            queue_capacity=100,
            batch_max_size=10,
            batch_timeout_seconds=1.0,
            backpressure_wait_ms=100,
            drop_on_full=True,
            sink_write=sink,
        )
        # Should have populated cached fields from default Settings()
        # Default sink_concurrency is 1 (no preset or env override)
        assert facade._cached_sink_concurrency == 1


class TestContractPresetEndToEnd:
    """AC5: Contract test — preset flows end-to-end."""

    def test_production_preset_all_cached_fields(self):
        """All production preset values reflected in cached fields."""
        logger = get_logger(name="test-contract", preset="production", reuse=False)
        assert logger._cached_sink_concurrency == 8
        assert logger._cached_adaptive_enabled is True
        assert logger._cached_adaptive_settings.max_workers == 4


class TestEnvVarOverrideWithoutPreset:
    """Env var override still wins when no preset is used."""

    def test_env_var_sink_concurrency(self, monkeypatch: pytest.MonkeyPatch):
        """FAPILOG__CORE__SINK_CONCURRENCY env var is respected without preset."""
        monkeypatch.setenv("FAPILOG_CORE__SINK_CONCURRENCY", "4")
        logger = get_logger(name="test-env", reuse=False)
        assert logger._cached_sink_concurrency == 4
