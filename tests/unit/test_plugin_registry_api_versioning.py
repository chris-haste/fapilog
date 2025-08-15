from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from fapilog.containers.container import AsyncLoggingContainer
from fapilog.plugins.registry import (
    AsyncComponentRegistry,
    PluginRegistryError,
)


@pytest.mark.asyncio
async def test_load_plugin_invalid_api_version_parse(tmp_path: Path) -> None:
    async with AsyncLoggingContainer() as container:
        registry = AsyncComponentRegistry(container)
        await registry.initialize()

        # Create a minimal local plugin file with a Plugin class
        plugin_file = tmp_path / "bad_api_plugin.py"
        plugin_file.write_text(
            """
class Plugin:
    async def start(self):
        return None
    async def stop(self):
        return None
    async def write(self, entry: dict):
        return None
"""
        )

        # Prepare a duck-typed metadata and plugin_info to bypass pydantic validators
        metadata = SimpleNamespace(
            name="bad-api-plugin",
            version="1.0.0",
            plugin_type="sink",
            entry_point=str(plugin_file),
            description="",
            author="t",
            api_version="bogus",  # invalid format to exercise parse error branch
        )
        plugin_info = SimpleNamespace(metadata=metadata, loaded=False, source="local")

        with patch(
            "fapilog.plugins.registry.validate_fapilog_compatibility", return_value=True
        ), patch.object(
            registry._discovery,
            "get_plugin_info",
            new=AsyncMock(return_value=plugin_info),
        ):
            with pytest.raises(PluginRegistryError, match="invalid api_version"):
                await registry.load_plugin("bad-api-plugin")


@pytest.mark.asyncio
async def test_load_plugin_incompatible_api_version_major(tmp_path: Path) -> None:
    async with AsyncLoggingContainer() as container:
        registry = AsyncComponentRegistry(container)
        await registry.initialize()

        plugin_file = tmp_path / "incompat_api_plugin.py"
        plugin_file.write_text(
            """
class Plugin:
    async def start(self):
        return None
    async def stop(self):
        return None
    async def write(self, entry: dict):
        return None
"""
        )

        # Valid-looking metadata but incompatible declared API (major mismatch)
        metadata = SimpleNamespace(
            name="incompat-api-plugin",
            version="1.0.0",
            plugin_type="sink",
            entry_point=str(plugin_file),
            description="",
            author="t",
            api_version="2.0",
        )
        plugin_info = SimpleNamespace(metadata=metadata, loaded=False, source="local")

        with patch(
            "fapilog.plugins.registry.validate_fapilog_compatibility", return_value=True
        ), patch.object(
            registry._discovery,
            "get_plugin_info",
            new=AsyncMock(return_value=plugin_info),
        ):
            with pytest.raises(PluginRegistryError, match="API 1.0"):
                await registry.load_plugin("incompat-api-plugin")


@pytest.mark.asyncio
async def test_registers_sink_with_protocol_component_type(tmp_path: Path) -> None:
    async with AsyncLoggingContainer() as container:
        registry = AsyncComponentRegistry(container)
        await registry.initialize()

        plugin_name = "protocol-sink"
        plugin_file = tmp_path / "protocol_sink.py"
        plugin_file.write_text(
            """
class Plugin:
    async def start(self):
        return None
    async def stop(self):
        return None
    async def write(self, entry: dict):
        return None
"""
        )

        # Compatible api_version
        metadata = SimpleNamespace(
            name=plugin_name,
            version="1.0.0",
            plugin_type="sink",
            entry_point=str(plugin_file),
            description="",
            author="t",
            api_version="1.0",
        )
        plugin_info = SimpleNamespace(metadata=metadata, loaded=False, source="local")

        with patch(
            "fapilog.plugins.registry.validate_fapilog_compatibility", return_value=True
        ), patch.object(
            registry._discovery,
            "get_plugin_info",
            new=AsyncMock(return_value=plugin_info),
        ), patch(
            "fapilog.core.plugin_config.validate_plugin_configuration"
        ) as mock_validate:

            class DummyValidation:
                def raise_if_error(self, *, plugin_name: str) -> None:
                    return None

            mock_validate.return_value = DummyValidation()
            instance = await registry.load_plugin(plugin_name)
            assert instance is not None
            # Verify container registration uses protocol type BaseSink via isolated name
            isolated = registry.get_isolated_name(plugin_name)
            info = container._components.get(isolated)  # type: ignore[attr-defined]
            from fapilog.plugins.sinks import BaseSink

            assert info is not None and info.component_type is BaseSink

            # Loading again should return cached instance (already loaded path)
            instance2 = await registry.load_plugin(plugin_name)
            assert instance2 is instance
