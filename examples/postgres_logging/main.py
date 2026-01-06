"""Example FastAPI app logging to PostgreSQL."""

from __future__ import annotations

from fastapi import Depends, FastAPI

import fapilog
from fapilog import get_async_logger

app = FastAPI()


async def get_logger():
    return await get_async_logger("api")


@app.get("/")
async def root(logger=Depends(get_logger)):  # type: ignore[override]
    await logger.info("Request received", path="/", method="GET")
    return {"status": "ok"}


@app.get("/users/{user_id}")
async def get_user(user_id: int, logger=Depends(get_logger)):  # type: ignore[override]
    await logger.info("User lookup", user_id=user_id)
    return {"user_id": user_id, "name": "Example User"}


@app.on_event("startup")
async def startup_event() -> None:
    # Ensure runtime wiring is initialized before handling requests
    fapilog.runtime()
