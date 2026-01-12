"""FastAPI one-liner logging setup."""

from __future__ import annotations

from fastapi import Depends, FastAPI

from fapilog.fastapi import get_request_logger, setup_logging

app = FastAPI(lifespan=setup_logging(preset="fastapi"))


@app.get("/")
async def root(logger=Depends(get_request_logger)):
    await logger.info("Request handled")
    return {"message": "Hello World"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
