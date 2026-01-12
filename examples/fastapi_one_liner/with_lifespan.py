"""FastAPI one-liner setup that wraps an existing lifespan."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from fapilog.fastapi import get_request_logger, setup_logging


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    app.state.startup_marker = True
    yield
    app.state.startup_marker = False


app = FastAPI(lifespan=setup_logging(wrap_lifespan=app_lifespan))


@app.get("/status")
async def status(logger=Depends(get_request_logger)) -> dict[str, bool]:
    await logger.info("Status requested")
    return {"ready": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("with_lifespan:app", host="0.0.0.0", port=8002, reload=True)
