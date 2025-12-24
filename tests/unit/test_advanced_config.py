from __future__ import annotations

import asyncio
from typing import Any, Mapping

import pytest

from fapilog.core import Settings
from fapilog.core.advanced_validation import validate_advanced_settings
from fapilog.core.change_detection import (
    compute_file_signature,
    signatures_differ,
)
from fapilog.core.errors import ConfigurationError
from fapilog.core.hot_reload import ConfigHotReloader
from fapilog.core.migration import migrate_to_latest, register_migration
from fapilog.core.plugin_config import ValidationResult


@pytest.mark.asyncio
async def test_compute_signature_and_diff(tmp_path) -> None:
    p = tmp_path / "conf.json"
    p.write_text("{}")
    sig1 = await compute_file_signature(str(p))
    p.write_text("{\n}\n")
    sig2 = await compute_file_signature(str(p))
    assert signatures_differ(sig1, sig2)


@pytest.mark.asyncio
async def test_watch_file_changes_handles_missing_file(tmp_path) -> None:
    """Test that watch_file_changes handles FileNotFoundError gracefully."""
    from fapilog.core.change_detection import watch_file_changes

    missing_file = tmp_path / "missing.txt"
    changes_detected = []

    async def on_change(event) -> None:
        changes_detected.append(event)

    # Create a stop event to control the watch loop
    stop_event = asyncio.Event()

    # Start watching a file that doesn't exist
    watch_task = asyncio.create_task(
        watch_file_changes(
            path=str(missing_file),
            on_change=on_change,
            stop_event=stop_event,
            interval_seconds=0.1,
        )
    )

    # Let it run for a short time to hit the FileNotFoundError path
    await asyncio.sleep(0.2)
    stop_event.set()

    # Wait for the task to complete
    try:
        await asyncio.wait_for(watch_task, timeout=1.0)
    except asyncio.TimeoutError:
        watch_task.cancel()
        try:
            await watch_task
        except asyncio.CancelledError:
            pass

    # The function should not have raised, even though the file was missing
    # (it should have handled FileNotFoundError and continued)


@pytest.mark.asyncio
async def test_hot_reload_calls_callbacks(tmp_path, monkeypatch) -> None:
    p = tmp_path / "c.json"
    p.write_text("{}")

    async def loader() -> Settings:
        # Minimal load via env only
        from fapilog.core.config import load_settings

        return await load_settings(env={})

    applied = []
    errors = []

    async def on_applied(s: Settings) -> None:
        applied.append(s)

    async def on_error(e: Exception) -> None:
        errors.append(e)

    reloader = ConfigHotReloader(
        path=str(p),
        loader=loader,
        on_applied=on_applied,
        on_error=on_error,
    )
    await reloader.start()
    try:
        p.write_text("{\n}\n")
        await asyncio.sleep(1.0)
        assert len(applied) >= 1
        assert len(errors) == 0
    finally:
        await reloader.stop()


@pytest.mark.asyncio
async def test_hot_reload_subscribe_and_notify(tmp_path) -> None:
    """Test subscribe functionality and notification to subscribers."""
    p = tmp_path / "c.json"
    p.write_text("{}")

    async def loader() -> Settings:
        from fapilog.core.config import load_settings

        return await load_settings(env={})

    applied = []
    subscriber_called = []

    async def on_applied(s: Settings) -> None:
        applied.append(s)

    async def subscriber(s: Settings) -> None:
        subscriber_called.append(s)

    reloader = ConfigHotReloader(
        path=str(p),
        loader=loader,
        on_applied=on_applied,
    )

    # Test subscribe method
    reloader.subscribe(subscriber)

    await reloader.start()
    try:
        p.write_text("{\n}\n")
        await asyncio.sleep(1.0)
        assert len(applied) >= 1
        assert len(subscriber_called) >= 1
    finally:
        await reloader.stop()


@pytest.mark.asyncio
async def test_hot_reload_with_validator(tmp_path) -> None:
    """Test hot reload with validation."""
    p = tmp_path / "c.json"
    p.write_text("{}")

    async def loader() -> Settings:
        from fapilog.core.config import load_settings

        return await load_settings(env={})

    async def validator(settings: Settings) -> ValidationResult:
        # Always return success for this test
        return ValidationResult(ok=True, issues=[])

    applied = []
    errors = []

    async def on_applied(s: Settings) -> None:
        applied.append(s)

    async def on_error(e: Exception) -> None:
        errors.append(e)

    reloader = ConfigHotReloader(
        path=str(p),
        loader=loader,
        validator=validator,
        on_applied=on_applied,
        on_error=on_error,
    )

    await reloader.start()
    try:
        p.write_text("{\n}\n")
        await asyncio.sleep(1.0)
        assert len(applied) >= 1
        assert len(errors) == 0
    finally:
        await reloader.stop()


@pytest.mark.asyncio
async def test_hot_reload_validation_error(tmp_path) -> None:
    """Test hot reload with validation error."""
    p = tmp_path / "c.json"
    p.write_text("{}")

    async def loader() -> Settings:
        from fapilog.core.config import load_settings

        return await load_settings(env={})

    async def validator(settings: Settings) -> ValidationResult:
        # Always return error for this test
        from fapilog.core.plugin_config import ValidationIssue

        return ValidationResult(
            ok=False, issues=[ValidationIssue(field="test", message="test error")]
        )

    applied = []
    errors = []

    async def on_applied(s: Settings) -> None:
        applied.append(s)

    async def on_error(e: Exception) -> None:
        errors.append(e)

    reloader = ConfigHotReloader(
        path=str(p),
        loader=loader,
        validator=validator,
        on_applied=on_applied,
        on_error=on_error,
    )

    await reloader.start()
    try:
        p.write_text("{\n}\n")
        await asyncio.sleep(1.0)
        # Should not be applied due to validation error
        assert len(applied) == 0
        # Should have error
        assert len(errors) >= 1
        assert isinstance(errors[0], ConfigurationError)
    finally:
        await reloader.stop()


@pytest.mark.asyncio
async def test_hot_reload_loader_error(tmp_path) -> None:
    """Test hot reload when loader raises an exception."""
    p = tmp_path / "c.json"
    p.write_text("{}")

    async def loader() -> Settings:
        raise ValueError("Loader error")

    applied = []
    errors = []

    async def on_applied(s: Settings) -> None:
        applied.append(s)

    async def on_error(e: Exception) -> None:
        errors.append(e)

    reloader = ConfigHotReloader(
        path=str(p),
        loader=loader,
        on_applied=on_applied,
        on_error=on_error,
    )

    await reloader.start()
    try:
        p.write_text("{\n}\n")
        await asyncio.sleep(1.0)
        # Should not be applied due to loader error
        assert len(applied) == 0
        # Should have error
        assert len(errors) >= 1
        assert isinstance(errors[0], ConfigurationError)
        error_msg = str(errors[0])
        assert "Hot reload failed" in error_msg
    finally:
        await reloader.stop()


@pytest.mark.asyncio
async def test_hot_reload_start_already_running(tmp_path) -> None:
    """Test starting hot reload when already running."""
    p = tmp_path / "c.json"
    p.write_text("{}")

    async def loader() -> Settings:
        from fapilog.core.config import load_settings

        return await load_settings(env={})

    reloader = ConfigHotReloader(path=str(p), loader=loader)

    # Start first time
    await reloader.start()
    assert reloader._task is not None

    # Start second time - should not create new task
    await reloader.start()
    assert reloader._task is not None

    await reloader.stop()


@pytest.mark.asyncio
async def test_hot_reload_stop_not_started(tmp_path) -> None:
    """Test stopping hot reload when not started."""
    p = tmp_path / "c.json"
    p.write_text("{}")

    async def loader() -> Settings:
        from fapilog.core.config import load_settings

        return await load_settings(env={})

    reloader = ConfigHotReloader(path=str(p), loader=loader)

    # Stop without starting - should not raise
    await reloader.stop()
    assert reloader._task is None
    assert reloader._stop_event is None


@pytest.mark.asyncio
async def test_hot_reload_stop_and_cleanup(tmp_path) -> None:
    """Test stopping hot reload and cleanup."""
    p = tmp_path / "c.json"
    p.write_text("{}")

    async def loader() -> Settings:
        from fapilog.core.config import load_settings

        return await load_settings(env={})

    reloader = ConfigHotReloader(path=str(p), loader=loader)

    await reloader.start()
    assert reloader._task is not None
    assert reloader._stop_event is not None

    await reloader.stop()
    assert reloader._task is None
    assert reloader._stop_event is None


@pytest.mark.asyncio
async def test_hot_reload_no_callbacks(tmp_path) -> None:
    """Test hot reload without any callbacks."""
    p = tmp_path / "c.json"
    p.write_text("{}")

    async def loader() -> Settings:
        from fapilog.core.config import load_settings

        return await load_settings(env={})

    reloader = ConfigHotReloader(
        path=str(p),
        loader=loader,
        # No on_applied or on_error callbacks
    )

    await reloader.start()
    try:
        p.write_text("{\n}\n")
        await asyncio.sleep(1.0)
        # Should not crash even without callbacks
    finally:
        await reloader.stop()


@pytest.mark.asyncio
async def test_advanced_validation_cross_field() -> None:
    s = Settings()
    # Core enables metrics, but observability.metrics is disabled by default
    s.core.enable_metrics = True
    result = await validate_advanced_settings(s)
    assert not result.ok
    assert any("observability.metrics.enabled" == i.field for i in result.issues)


@pytest.mark.asyncio
async def test_advanced_validation_access_control_admin_role() -> None:
    """Test that access control requires 'admin' role when enabled."""
    s = Settings()
    s.security.access_control.enabled = True
    s.security.access_control.allowed_roles = ["user", "editor"]  # No admin
    result = await validate_advanced_settings(s)
    assert not result.ok
    assert any(
        "security.access_control.allowed_roles" == i.field
        and "admin" in i.message.lower()
        for i in result.issues
    )


@pytest.mark.asyncio
async def test_advanced_validation_tracing_without_metrics_warning() -> None:
    """Test informational warning when tracing is enabled without metrics."""
    s = Settings()
    s.observability.tracing.enabled = True
    s.observability.metrics.enabled = False
    result = await validate_advanced_settings(s)
    # Should have a warning (not an error)
    assert any(
        "observability.tracing.enabled" == i.field
        and i.severity == "warn"
        and "metrics" in i.message.lower()
        for i in result.issues
    )


def test_migration_default_and_custom() -> None:
    data = {"schema_version": "0.9", "core": {"app_name": "x"}}

    def bump_to_1_0(d: Mapping[str, Any]) -> Mapping[str, Any]:
        nd = dict(d)
        nd["schema_version"] = "1.0"
        return nd

    register_migration("0.9", bump_to_1_0)
    res = migrate_to_latest(data)
    assert res.did_migrate is True
    assert res.to_version == "1.0"


def test_migration_no_migration_needed() -> None:
    """Test migration when version is already latest."""
    from fapilog.core.settings import LATEST_CONFIG_SCHEMA_VERSION

    data = {"schema_version": LATEST_CONFIG_SCHEMA_VERSION, "core": {"app_name": "x"}}
    res = migrate_to_latest(data)
    assert res.did_migrate is False
    assert res.from_version == LATEST_CONFIG_SCHEMA_VERSION
    assert res.to_version == LATEST_CONFIG_SCHEMA_VERSION


def test_migration_cycle_detection() -> None:
    """Test that migration detects and prevents cycles."""
    data = {"schema_version": "0.8", "core": {"app_name": "x"}}

    def create_cycle(version: str):
        def migrator(d: Mapping[str, Any]) -> Mapping[str, Any]:
            nd = dict(d)
            nd["schema_version"] = version
            return nd

        return migrator

    # Create a cycle: 0.8 -> 0.9 -> 0.8
    register_migration("0.8", create_cycle("0.9"))
    register_migration("0.9", create_cycle("0.8"))

    res = migrate_to_latest(data)
    # Should break the cycle and set to latest version
    from fapilog.core.settings import LATEST_CONFIG_SCHEMA_VERSION

    assert res.to_version == LATEST_CONFIG_SCHEMA_VERSION
    # Should have migrated at least once before detecting cycle
    assert res.did_migrate is True


def test_migration_default_when_no_migrator() -> None:
    """Test that migration uses default (version bump) when no migrator registered."""
    from fapilog.core.migration import _MIGRATIONS
    from fapilog.core.settings import LATEST_CONFIG_SCHEMA_VERSION

    # Clear any existing migrations for the test version
    test_version = "0.7"
    original_migrator = _MIGRATIONS.pop(test_version, None)

    try:
        data = {"schema_version": test_version, "core": {"app_name": "x"}}
        res = migrate_to_latest(data)
        assert res.did_migrate is True
        assert res.to_version == LATEST_CONFIG_SCHEMA_VERSION
        assert res.from_version == test_version
    finally:
        # Restore original migrator if it existed
        if original_migrator is not None:
            _MIGRATIONS[test_version] = original_migrator
