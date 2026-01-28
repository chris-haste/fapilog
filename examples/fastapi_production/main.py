"""
FastAPI Production Template with Fapilog.

This example demonstrates production-ready logging setup including:
- Structured JSON logging via setup_logging()
- Request correlation IDs (automatic)
- Metrics endpoint (Prometheus-compatible)
- Health check endpoint
- Graceful shutdown (handled by setup_logging)

Run:
    pip install fapilog[fastapi] uvicorn prometheus-client
    uvicorn examples.fastapi_production.main:app --reload
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, Response
from fastapi.responses import JSONResponse

from fapilog.core.errors import request_id_var
from fapilog.fastapi import get_request_logger, setup_logging

# Create app with fapilog's setup_logging lifespan
# This handles: logger init, middleware registration, graceful shutdown
app = FastAPI(
    title="FastAPI + Fapilog Production Template",
    version="1.0.0",
    lifespan=setup_logging(
        preset="fastapi",
        skip_paths=["/health", "/metrics"],  # Don't log health/metrics requests
    ),
)


@app.get("/")
async def root(logger: Any = Depends(get_request_logger)) -> dict[str, str]:
    """Example endpoint with structured logging."""
    await logger.info("root_endpoint_called")
    request_id = request_id_var.get("unknown")
    return {"message": "Hello, World!", "request_id": request_id}


@app.get("/health", response_model=None)
async def health_check() -> dict[str, str] | Response:
    """Health check endpoint for load balancers/orchestrators.

    Returns 200 if healthy, 503 if unhealthy.
    """
    # Check if logger is available via app state
    logger = getattr(app.state, "fapilog_logger", None)
    logger_healthy = logger is not None and not getattr(logger, "_drained", True)

    if logger_healthy:
        return {"status": "healthy", "logger": "ok"}
    else:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "logger": "not ready"},
        )


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus-compatible metrics endpoint.

    For full Prometheus integration, install prometheus-client.
    """
    try:
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

        from fapilog.core.observability import (
            ObservabilitySettings,
            create_metrics_collector_from_settings,
        )

        metrics_collector = create_metrics_collector_from_settings(
            ObservabilitySettings(metrics={"enabled": True, "exporter": "prometheus"})
        )
        registry = metrics_collector.registry
        if registry is not None:
            payload = generate_latest(registry)
            return Response(content=payload, media_type=CONTENT_TYPE_LATEST)
        return Response(content="# No metrics available\n", media_type="text/plain")
    except ImportError:
        # Fallback if prometheus_client not installed
        logger = getattr(app.state, "fapilog_logger", None)
        content = "# fapilog metrics (install prometheus-client for full support)\n"
        content += f"# logger_active {1 if logger is not None else 0}\n"
        return Response(content=content, media_type="text/plain")


@app.get("/error")
async def trigger_error(logger: Any = Depends(get_request_logger)) -> dict[str, str]:
    """Example endpoint that demonstrates error logging."""
    try:
        raise ValueError("Intentional error for demonstration")
    except Exception:
        await logger.exception("error_endpoint_triggered")
        return {"error": "An error was logged"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
