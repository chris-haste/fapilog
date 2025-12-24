from __future__ import annotations

from types import SimpleNamespace

import pytest

from fapilog.plugins.discovery import AsyncPluginDiscovery


def _stub_entry_points() -> SimpleNamespace:
    return SimpleNamespace(select=lambda *, group: [], get=lambda _g, default=None: [])


def _stub_distributions() -> list[object]:
    return []


@pytest.mark.asyncio
async def test_discover_all_offloads_blocking_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_to_thread(fn, *args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(getattr(fn, "__name__", "anon"))
        return fn(*args, **kwargs)

    monkeypatch.setattr("fapilog.plugins.discovery.asyncio.to_thread", fake_to_thread)
    monkeypatch.setattr("importlib.metadata.entry_points", _stub_entry_points)
    monkeypatch.setattr("importlib.metadata.distributions", _stub_distributions)

    disc = AsyncPluginDiscovery()
    plugins = await disc.discover_all_plugins()

    assert plugins == {}
    # Expect at least entry_points and distributions to be offloaded
    assert len(calls) >= 2


@pytest.mark.asyncio
async def test_discover_all_without_offload(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_to_thread(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("to_thread should not be called when offload disabled")

    monkeypatch.setattr("fapilog.plugins.discovery.asyncio.to_thread", raise_to_thread)
    monkeypatch.setattr("importlib.metadata.entry_points", _stub_entry_points)
    monkeypatch.setattr("importlib.metadata.distributions", _stub_distributions)

    disc = AsyncPluginDiscovery(offload_blocking=False)
    plugins = await disc.discover_all_plugins()

    assert plugins == {}


@pytest.mark.asyncio
async def test_entry_point_load_offloaded(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def fake_to_thread(fn, *args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(getattr(fn, "__name__", "anon"))
        return fn(*args, **kwargs)

    plugin_module = type(
        "PluginMod", (), {"PLUGIN_METADATA": {"name": "ep", "version": "0.0.1"}}
    )

    class EP:
        name = "ep"
        group = "fapilog.sinks"

        def load(self):
            return plugin_module

    monkeypatch.setattr("fapilog.plugins.discovery.asyncio.to_thread", fake_to_thread)
    monkeypatch.setattr(
        "importlib.metadata.entry_points",
        lambda: SimpleNamespace(
            select=lambda *, group=None: [EP()], get=lambda _g, default=None: [EP()]
        ),
    )
    monkeypatch.setattr("importlib.metadata.distributions", _stub_distributions)

    disc = AsyncPluginDiscovery()
    await disc.discover_all_plugins()

    assert "load" in calls


@pytest.mark.asyncio
async def test_entry_points_cache_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    call_count = 0

    def entry_points():
        nonlocal call_count
        call_count += 1
        return SimpleNamespace(
            select=lambda *, group=None: [], get=lambda _g, default=None: []
        )

    class Dist:
        def __init__(self) -> None:
            self.metadata = {"Name": "fapilog-test", "Keywords": ""}

    monkeypatch.setattr("importlib.metadata.entry_points", entry_points)
    monkeypatch.setattr("importlib.metadata.distributions", lambda: [Dist()])

    disc = AsyncPluginDiscovery()
    await disc.discover_all_plugins()

    assert call_count == 1
