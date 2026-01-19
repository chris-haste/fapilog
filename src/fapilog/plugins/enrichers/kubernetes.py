from __future__ import annotations

import os
import re
from typing import Any

from pydantic import BaseModel, ConfigDict

from ..utils import parse_plugin_config


class KubernetesEnricherConfig(BaseModel):
    """Configuration for KubernetesEnricher."""

    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)

    prefix: str = "k8s_"
    skip_if_not_k8s: bool = True

    pod_name_env: str = "POD_NAME"
    pod_namespace_env: str = "POD_NAMESPACE"
    node_name_env: str = "NODE_NAME"
    container_name_env: str = "CONTAINER_NAME"
    cluster_name_env: str = "CLUSTER_NAME"


_DEPLOYMENT_PATTERN = re.compile(r"^(.+)-[a-f0-9]{8,10}-[a-z0-9]{5}$")
_STATEFULSET_PATTERN = re.compile(r"^(.+)-\d+$")
_DAEMONSET_PATTERN = re.compile(r"^(.+)-[a-z0-9]{5}$")


def _extract_deployment_name(pod_name: str) -> str | None:
    """Best-effort extraction of deployment/statefulset/daemonset name."""
    match = _DEPLOYMENT_PATTERN.match(pod_name)
    if match:
        return match.group(1)
    match = _STATEFULSET_PATTERN.match(pod_name)
    if match:
        return match.group(1)
    match = _DAEMONSET_PATTERN.match(pod_name)
    if match:
        return match.group(1)
    return None


class KubernetesEnricher:
    """Enrich log entries with Kubernetes pod metadata."""

    name = "kubernetes"

    def __init__(
        self,
        config: KubernetesEnricherConfig | dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self._config = parse_plugin_config(KubernetesEnricherConfig, config, **kwargs)
        self._cached_fields: dict[str, Any] = {}

    async def start(self) -> None:
        self._cached_fields = self._build_cached_fields()

    async def stop(self) -> None:  # pragma: no cover - no resources to release
        return None

    async def enrich(self, event: dict[str, Any]) -> dict[str, Any]:
        """Return Kubernetes metadata targeting the diagnostics semantic group.

        Returns:
            Dict with structure: {"diagnostics": {"k8s_pod": ..., "k8s_namespace": ..., ...}}
        """
        return {"diagnostics": dict(self._cached_fields)}

    async def health_check(self) -> bool:
        return True

    def _build_cached_fields(self) -> dict[str, Any]:
        cfg = self._config
        pod_name = os.getenv(cfg.pod_name_env)
        if not pod_name and cfg.skip_if_not_k8s:
            return {}

        fields: dict[str, Any] = {}
        prefix = cfg.prefix

        if pod_name:
            fields[f"{prefix}pod"] = pod_name

        namespace = os.getenv(cfg.pod_namespace_env)
        if namespace:
            fields[f"{prefix}namespace"] = namespace

        node = os.getenv(cfg.node_name_env)
        if node:
            fields[f"{prefix}node"] = node

        container = os.getenv(cfg.container_name_env)
        if container:
            fields[f"{prefix}container"] = container

        cluster = os.getenv(cfg.cluster_name_env)
        if cluster:
            fields[f"{prefix}cluster"] = cluster

        if pod_name:
            deployment = _extract_deployment_name(pod_name)
            if deployment:
                fields[f"{prefix}deployment"] = deployment

        return fields


PLUGIN_METADATA = {
    "name": "kubernetes",
    "version": "1.1.0",
    "plugin_type": "enricher",
    "entry_point": "fapilog.plugins.enrichers.kubernetes:KubernetesEnricher",
    "description": "Adds K8s pod metadata (pod, namespace, node, deployment) to diagnostics group.",
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "0.3.0"},
    "api_version": "1.1",
}


__all__ = ["KubernetesEnricher", "KubernetesEnricherConfig"]
