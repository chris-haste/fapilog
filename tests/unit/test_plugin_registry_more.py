from __future__ import annotations

from types import SimpleNamespace

import pytest

from fapilog.containers.container import AsyncLoggingContainer
from fapilog.plugins.registry import AsyncComponentRegistry, PluginLoadError


@pytest.mark.asyncio
async def test_load_plugin_instance_unknown_source_raises() -> None:
    async with AsyncLoggingContainer() as container:
        registry = AsyncComponentRegistry(container)
        await registry.initialize()

        plugin_info = SimpleNamespace(
            metadata=SimpleNamespace(name="x", entry_point="/tmp/x.py"),
            source="weird",
        )
        with pytest.raises(PluginLoadError, match="Unknown plugin source"):
            await registry._load_plugin_instance(plugin_info)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_register_with_container_swallows_errors() -> None:
    async with AsyncLoggingContainer() as container:
        registry = AsyncComponentRegistry(container)
        await registry.initialize()

        class Dummy:
            pass

        # Force container.register_component to raise
        def _boom(**kwargs):
            raise RuntimeError("x")

        container.register_component = _boom  # type: ignore[assignment]
        # Should not raise
        await registry._register_with_container(
            plugin_name="d",
            plugin_info=SimpleNamespace(),  # type: ignore[arg-type]
            instance=Dummy(),
        )
