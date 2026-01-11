from __future__ import annotations

import sys
import types

from fapilog.plugins import loader
from fapilog.plugins.enrichers.context_vars import (
    PLUGIN_METADATA as CONTEXT_META,
)
from fapilog.plugins.enrichers.context_vars import (
    ContextVarsEnricher,
)
from fapilog.plugins.enrichers.kubernetes import (
    PLUGIN_METADATA as KUBERNETES_META,
)
from fapilog.plugins.enrichers.kubernetes import (
    KubernetesEnricher,
)
from fapilog.plugins.enrichers.runtime_info import (
    PLUGIN_METADATA as RUNTIME_META,
)
from fapilog.plugins.enrichers.runtime_info import (
    RuntimeInfoEnricher,
)
from fapilog.plugins.processors.size_guard import (
    PLUGIN_METADATA as SIZE_GUARD_META,
)
from fapilog.plugins.processors.size_guard import (
    SizeGuardProcessor,
)
from fapilog.plugins.processors.zero_copy import (
    PLUGIN_METADATA as ZERO_COPY_META,
)
from fapilog.plugins.processors.zero_copy import (
    ZeroCopyProcessor,
)
from fapilog.plugins.sinks.contrib.cloudwatch import (
    PLUGIN_METADATA as CLOUDWATCH_META,
)
from fapilog.plugins.sinks.contrib.cloudwatch import (
    CloudWatchSink,
)
from fapilog.plugins.sinks.contrib.loki import (
    PLUGIN_METADATA as LOKI_META,
)
from fapilog.plugins.sinks.contrib.loki import (
    LokiSink,
)
from fapilog.plugins.sinks.contrib.postgres import (
    PLUGIN_METADATA as POSTGRES_META,
)
from fapilog.plugins.sinks.contrib.postgres import (
    PostgresSink,
)
from fapilog.plugins.sinks.rotating_file import (
    PLUGIN_METADATA as ROTATING_FILE_META,
)
from fapilog.plugins.sinks.rotating_file import (
    RotatingFileSink,
)
from fapilog.plugins.sinks.routing import (
    PLUGIN_METADATA as ROUTING_META,
)
from fapilog.plugins.sinks.routing import (
    RoutingSink,
)
from fapilog.plugins.sinks.stdout_json import (
    PLUGIN_METADATA as STDOUT_META,
)
from fapilog.plugins.sinks.stdout_json import (
    StdoutJsonSink,
)
from fapilog.plugins.sinks.stdout_pretty import (
    PLUGIN_METADATA as STDOUT_PRETTY_META,
)
from fapilog.plugins.sinks.stdout_pretty import (
    StdoutPrettySink,
)
from fapilog.plugins.utils import normalize_plugin_name


def test_builtin_metadata_matches_class_names() -> None:
    cases = [
        (ContextVarsEnricher, CONTEXT_META),
        (RuntimeInfoEnricher, RUNTIME_META),
        (KubernetesEnricher, KUBERNETES_META),
        (ZeroCopyProcessor, ZERO_COPY_META),
        (SizeGuardProcessor, SIZE_GUARD_META),
        (StdoutJsonSink, STDOUT_META),
        (StdoutPrettySink, STDOUT_PRETTY_META),
        (RotatingFileSink, ROTATING_FILE_META),
        (CloudWatchSink, CLOUDWATCH_META),
        (LokiSink, LOKI_META),
        (PostgresSink, POSTGRES_META),
        (RoutingSink, ROUTING_META),
    ]

    for cls, meta in cases:
        assert normalize_plugin_name(cls.name) == normalize_plugin_name(meta["name"])


def test_warn_on_name_mismatch(monkeypatch) -> None:
    calls: list[dict] = []

    def fake_warn(category, message, **attrs):  # noqa: D401
        calls.append({"category": category, "message": message, "attrs": attrs})

    monkeypatch.setattr(loader, "diagnostics", types.SimpleNamespace(warn=fake_warn))

    mod = types.ModuleType("fake_plugin_mod")
    mod.PLUGIN_METADATA = {"name": "meta-name"}
    monkeypatch.setitem(sys.modules, "fake_plugin_mod", mod)

    class Dummy:
        __module__ = "fake_plugin_mod"
        name = "class_name"

    loader._warn_on_name_mismatch(Dummy)

    assert calls
    call = calls[0]
    assert call["category"] == "plugins"
    assert call["attrs"]["class_name"] == "class_name"
    assert call["attrs"]["metadata_name"] == "meta-name"
    assert call["attrs"]["plugin"] == "Dummy"


def test_warn_on_name_mismatch_skips_normalized_equivalents(monkeypatch) -> None:
    calls: list[dict] = []

    def fake_warn(*_args, **_kwargs):
        calls.append({})

    monkeypatch.setattr(loader, "diagnostics", types.SimpleNamespace(warn=fake_warn))

    mod = types.ModuleType("fake_plugin_mod2")
    mod.PLUGIN_METADATA = {"name": "my-plugin"}
    monkeypatch.setitem(sys.modules, "fake_plugin_mod2", mod)

    class Dummy2:
        __module__ = "fake_plugin_mod2"
        name = "my_plugin"

    loader._warn_on_name_mismatch(Dummy2)

    assert calls == []


def test_loader_supports_legacy_enricher_aliases() -> None:
    plugin = loader.load_plugin("fapilog.enrichers", "context-vars-enricher", {})
    assert isinstance(plugin, ContextVarsEnricher)
