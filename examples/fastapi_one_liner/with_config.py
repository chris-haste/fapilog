"""FastAPI one-liner setup with middleware configuration."""

from __future__ import annotations

from fastapi import Depends, FastAPI

from fapilog.fastapi import get_request_logger, setup_logging

app = FastAPI(
    lifespan=setup_logging(
        preset="production",
        skip_paths=["/health", "/metrics"],
        sample_rate=0.1,
        redact_headers=["authorization", "cookie"],
    )
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/users/{user_id}")
async def get_user(user_id: int, logger=Depends(get_request_logger)):
    await logger.info("Fetching user", user_id=user_id)
    return {"user_id": user_id}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("with_config:app", host="0.0.0.0", port=8001, reload=True)
