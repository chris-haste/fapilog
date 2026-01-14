"""Example FastAPI app logging to PostgreSQL."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from fapilog import get_async_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Logger is created once at startup
    app.state.logger = await get_async_logger("api")
    yield
    # Drain on shutdown
    await app.state.logger.drain()


app = FastAPI(lifespan=lifespan)


async def get_logger():
    return app.state.logger


@app.get("/")
async def root(logger=Depends(get_logger)):  # type: ignore[override]
    await logger.info("Request received", path="/", method="GET")
    return {"status": "ok"}


@app.get("/users/{user_id}")
async def get_user(user_id: int, logger=Depends(get_logger)):  # type: ignore[override]
    await logger.info("User lookup", user_id=user_id)
    return {"user_id": user_id, "name": "Example User"}
