from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fapilog.containers.container import AsyncLoggingContainer
from fapilog.plugins.registry import AsyncComponentRegistry, PluginRegistryError


def _make_plugin_info_local(path: str) -> SimpleNamespace:
    # Minimal pydantic-free structure duck-typed for registry._load_plugin_instance
    metadata = SimpleNamespace(
        name="demo-plugin",
        version="1.0.0",
        plugin_type="sink",
        entry_point=path,
        description="",
        author="t",
        api_version="1.0",
    )
    return SimpleNamespace(metadata=metadata, loaded=False, source="local")


@pytest.mark.asyncio
async def test_denylist_blocks_plugin() -> None:
    async with AsyncLoggingContainer() as container:
        registry = AsyncComponentRegistry(container)
        await registry.initialize()

        with patch(
            "fapilog.plugins.registry.validate_fapilog_compatibility", return_value=True
        ), patch("fapilog.core.settings.Settings") as MockSettings, patch.object(
            registry._discovery,
            "get_plugin_info",
            new=AsyncMock(return_value=_make_plugin_info_local("/tmp/x.py")),
        ):
            cfg = MockSettings.return_value
            cfg.plugins.denylist = ["demo-plugin"]
            cfg.plugins.allowlist = []
            with pytest.raises(PluginRegistryError, match="denied by configuration"):
                await registry.load_plugin("demo-plugin")


@pytest.mark.asyncio
async def test_allowlist_blocks_nonlisted_plugin() -> None:
    async with AsyncLoggingContainer() as container:
        registry = AsyncComponentRegistry(container)
        await registry.initialize()

        with patch(
            "fapilog.plugins.registry.validate_fapilog_compatibility", return_value=True
        ), patch("fapilog.core.settings.Settings") as MockSettings, patch.object(
            registry._discovery,
            "get_plugin_info",
            new=AsyncMock(return_value=_make_plugin_info_local("/tmp/x.py")),
        ):
            cfg = MockSettings.return_value
            cfg.plugins.denylist = []
            cfg.plugins.allowlist = ["only-this"]
            with pytest.raises(PluginRegistryError, match="not in allowlist"):
                await registry.load_plugin("demo-plugin")


@pytest.mark.asyncio
async def test_initialize_applies_discovery_paths() -> None:
    async with AsyncLoggingContainer() as container:
        registry = AsyncComponentRegistry(container)
        with patch("fapilog.core.settings.Settings") as MockSettings:
            cfg = MockSettings.return_value
            cfg.plugins.enabled = True
            cfg.plugins.discovery_paths = ["/opt/fapilog/plugins", "/tmp/plugins"]
            # Spy on add_discovery_path
            spy = MagicMock()
            registry._discovery.add_discovery_path = spy  # type: ignore[assignment]
            await registry.initialize()
            assert spy.call_count == 2


@pytest.mark.asyncio
async def test_initialize_eager_plugins_loads_targets() -> None:
    async with AsyncLoggingContainer() as container:
        registry = AsyncComponentRegistry(container)
        await registry.initialize()

        with patch("fapilog.core.settings.Settings") as MockSettings:
            cfg = MockSettings.return_value
            cfg.plugins.load_on_startup = ["a", "b", "c"]
            calls: list[str] = []

            async def _fake_load(name: str) -> None:
                calls.append(name)

            registry.load_plugin = _fake_load  # type: ignore[assignment]
            await registry.initialize_eager_plugins()
            assert calls == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_load_plugins_by_type_swallows_errors() -> None:
    async with AsyncLoggingContainer() as container:
        registry = AsyncComponentRegistry(container)
        await registry.initialize()

        with patch.object(
            registry,
            "discover_plugins",
            new=AsyncMock(return_value={"p1": SimpleNamespace()}),
        ):

            async def _boom(_name: str) -> None:
                raise RuntimeError("x")

            registry.load_plugin = _boom  # type: ignore[assignment]
            result = await registry.load_plugins_by_type("sink")
            assert result == {}


@pytest.mark.asyncio
async def test_get_plugin_wrong_type_returns_none() -> None:
    async with AsyncLoggingContainer() as container:
        registry = AsyncComponentRegistry(container)
        await registry.initialize()

        with patch.object(
            registry._lifecycle_manager,
            "get_component",
            new=AsyncMock(return_value=object()),
        ):
            got = await registry.get_plugin("name", int)
            assert got is None


@pytest.mark.asyncio
async def test_unload_plugin_nonexistent_noop() -> None:
    async with AsyncLoggingContainer() as container:
        registry = AsyncComponentRegistry(container)
        await registry.initialize()
        # Should not raise
        await registry.unload_plugin("missing")
