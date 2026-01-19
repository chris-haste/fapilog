from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from fapilog.plugins.enrichers.kubernetes import (
    KubernetesEnricher,
    KubernetesEnricherConfig,
    _extract_deployment_name,
)


class TestDeploymentExtraction:
    def test_deployment_pattern(self) -> None:
        assert _extract_deployment_name("my-app-7d4b8c9f6-abc12") == "my-app"
        assert _extract_deployment_name("api-server-6f9c5d8b7a-xyzpq") == "api-server"

    def test_statefulset_pattern(self) -> None:
        assert _extract_deployment_name("redis-0") == "redis"
        assert _extract_deployment_name("postgres-master-2") == "postgres-master"

    def test_daemonset_pattern(self) -> None:
        assert _extract_deployment_name("fluent-bit-abc12") == "fluent-bit"

    def test_unrecognized_pattern_returns_none(self) -> None:
        assert _extract_deployment_name("simple-pod") is None

    def test_deployment_pattern_takes_priority_over_daemonset(self) -> None:
        """Deployment pattern (replicaset-hash + pod-hash) should match before DaemonSet."""
        # This pod name matches Deployment pattern (8-10 char hex + 5 char suffix)
        # and would also match DaemonSet pattern (5 char suffix) if checked first.
        # Deployment pattern should win.
        result = _extract_deployment_name("my-app-7d4b8c9f6-abc12")
        assert result == "my-app"
        # The full ReplicaSet suffix should NOT be included
        assert result != "my-app-7d4b8c9f6"

    def test_ambiguous_5char_suffix_matches_daemonset(self) -> None:
        """A 5-char alphanumeric suffix without replicaset hash matches DaemonSet."""
        # No 8-10 char hex segment, so this is DaemonSet pattern
        assert _extract_deployment_name("node-exporter-x7k2m") == "node-exporter"

    def test_complex_app_name_with_hyphens(self) -> None:
        """App names with multiple hyphens should extract correctly."""
        # Deployment with hyphenated app name
        assert _extract_deployment_name("my-cool-app-7d4b8c9f6-abc12") == "my-cool-app"
        # StatefulSet with hyphenated app name
        assert _extract_deployment_name("my-cool-app-0") == "my-cool-app"
        # DaemonSet with hyphenated app name
        assert _extract_deployment_name("my-cool-app-x7k2m") == "my-cool-app"

    def test_replicaset_hash_boundary_lengths(self) -> None:
        """ReplicaSet hash can be 8-10 hex chars."""
        # 8-char hash (minimum)
        assert _extract_deployment_name("app-12345678-abc12") == "app"
        # 9-char hash
        assert _extract_deployment_name("app-123456789-abc12") == "app"
        # 10-char hash (maximum)
        assert _extract_deployment_name("app-1234567890-abc12") == "app"

    def test_non_deployment_patterns_fall_through_to_daemonset(self) -> None:
        """Patterns that don't match Deployment/StatefulSet fall back to DaemonSet."""
        # 7-char hash (too short for Deployment) - matches DaemonSet pattern
        # Returns "app-1234567" since DaemonSet just strips the 5-char suffix
        assert _extract_deployment_name("app-1234567-abc12") == "app-1234567"
        # 11-char hash (too long for Deployment) - matches DaemonSet pattern
        assert _extract_deployment_name("app-12345678901-abc12") == "app-12345678901"

    def test_no_match_returns_none(self) -> None:
        """Patterns that don't match any known format return None."""
        # Single word with no hyphen
        assert _extract_deployment_name("standalone") is None
        # Too short suffix (< 5 chars)
        assert _extract_deployment_name("app-abc") is None
        # Suffix with invalid chars for all patterns
        assert _extract_deployment_name("app-ABC12") is None  # uppercase not matched


@pytest.fixture
def k8s_env() -> dict[str, str]:
    env = {
        "POD_NAME": "my-app-7d4b8c9f6-abc12",
        "POD_NAMESPACE": "production",
        "NODE_NAME": "node-1",
        "CONTAINER_NAME": "main",
        "CLUSTER_NAME": "prod-cluster",
    }
    with patch.dict(os.environ, env, clear=True):
        yield env


@pytest.mark.asyncio
async def test_returns_diagnostics_structure(k8s_env: dict[str, str]) -> None:
    """KubernetesEnricher returns nested structure targeting diagnostics group."""
    enricher = KubernetesEnricher()
    await enricher.start()
    result = await enricher.enrich({})

    assert "diagnostics" in result
    assert isinstance(result["diagnostics"], dict)
    # Should not have flat top-level k8s fields
    assert "k8s_pod" not in result


@pytest.mark.asyncio
async def test_diagnostics_contains_k8s_fields(k8s_env: dict[str, str]) -> None:
    """Diagnostics group contains all K8s metadata."""
    enricher = KubernetesEnricher()
    await enricher.start()
    result = await enricher.enrich({})

    diag = result["diagnostics"]
    assert diag["k8s_pod"] == k8s_env["POD_NAME"]
    assert diag["k8s_namespace"] == k8s_env["POD_NAMESPACE"]
    assert diag["k8s_node"] == k8s_env["NODE_NAME"]
    assert diag["k8s_container"] == k8s_env["CONTAINER_NAME"]
    assert diag["k8s_cluster"] == k8s_env["CLUSTER_NAME"]
    assert diag["k8s_deployment"] == "my-app"


@pytest.mark.asyncio
async def test_enricher_respects_custom_prefix() -> None:
    with patch.dict(os.environ, {"POD_NAME": "test-pod"}, clear=True):
        enricher = KubernetesEnricher(prefix="kube_")
        await enricher.start()
        result = await enricher.enrich({})

    diag = result["diagnostics"]
    assert "kube_pod" in diag
    assert "k8s_pod" not in diag


@pytest.mark.asyncio
async def test_enricher_noop_when_not_in_k8s() -> None:
    """Returns empty diagnostics when not in K8s environment."""
    with patch.dict(os.environ, {}, clear=True):
        enricher = KubernetesEnricher()
        await enricher.start()
        result = await enricher.enrich({})

    assert "diagnostics" in result
    assert result["diagnostics"] == {}


@pytest.mark.asyncio
async def test_enricher_can_force_fields_when_not_in_k8s() -> None:
    with patch.dict(os.environ, {"POD_NAMESPACE": "default"}, clear=True):
        enricher = KubernetesEnricher(skip_if_not_k8s=False)
        await enricher.start()
        result = await enricher.enrich({})

    diag = result["diagnostics"]
    assert diag.get("k8s_namespace") == "default"


@pytest.mark.asyncio
async def test_enricher_uses_custom_env_names() -> None:
    env: dict[str, str] = {
        "CUSTOM_POD": "api-0",
        "CUSTOM_NS": "staging",
    }
    with patch.dict(os.environ, env, clear=True):
        enricher = KubernetesEnricher(
            KubernetesEnricherConfig(
                pod_name_env="CUSTOM_POD", pod_namespace_env="CUSTOM_NS"
            )
        )
        await enricher.start()
        result = await enricher.enrich({})

    diag = result["diagnostics"]
    assert diag["k8s_pod"] == "api-0"
    assert diag["k8s_namespace"] == "staging"
    assert diag["k8s_deployment"] == "api"


@pytest.mark.asyncio
async def test_enricher_cached_results_are_copies() -> None:
    with patch.dict(os.environ, {"POD_NAME": "pod-1"}, clear=True):
        enricher = KubernetesEnricher()
        await enricher.start()
        first = await enricher.enrich({})
        second = await enricher.enrich({})

    assert first == second
    assert first is not second
    # Verify diagnostics dict is also a copy
    assert first["diagnostics"] is not second["diagnostics"]


def test_config_validation_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        KubernetesEnricher(config={"unknown": True})  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_enricher_health_check_always_returns_true() -> None:
    """Health check returns True even when not in K8s (graceful degradation)."""
    with patch.dict(os.environ, {}, clear=True):
        enricher = KubernetesEnricher()
        await enricher.start()
        assert await enricher.health_check() is True
