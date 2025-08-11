"""
Minimal FastAPI example exposing Fapilog's Prometheus metrics.

Run:
    pip install fastapi uvicorn
    uvicorn examples.fastapi_metrics.main:app --reload
"""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from fapilog.core.observability import (
    ObservabilitySettings,
    create_metrics_collector_from_settings,
)
from fapilog.metrics.metrics import plugin_timer

app = FastAPI(title="Fapilog Metrics Example")

# Enable Prometheus exporter in the collector's isolated registry
metrics = create_metrics_collector_from_settings(
    ObservabilitySettings(metrics={"enabled": True, "exporter": "prometheus"})
)


@app.get("/metrics")
async def metrics_endpoint() -> Response:
    """Expose Prometheus metrics for scraping (e.g., by Prometheus server)."""
    registry = metrics.registry
    if registry is None:
        return Response(status_code=204)
    payload = generate_latest(registry)
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)


@app.get("/simulate")
async def simulate_work() -> dict[str, bool]:
    """Simulate a single plugin execution and record an event metric.

    Use the reusable plugin_timer context to automatically record latency and
    error metrics for a synthetic plugin call.
    """
    async with plugin_timer(metrics, "DemoPlugin"):
        await asyncio.sleep(0.01)
    await metrics.record_event_processed()
    return {"ok": True}
