"""Minimal FastAPI app logging to Loki."""

import os

from fastapi import FastAPI

import fapilog

app = FastAPI()


@app.on_event("startup")
async def setup_logging() -> None:
    os.environ.setdefault("FAPILOG_CORE__SINKS", '["loki"]')
    os.environ.setdefault("FAPILOG_LOKI__URL", "http://localhost:3100")
    os.environ.setdefault(
        "FAPILOG_LOKI__LABELS", '{"service":"example-app","env":"local"}'
    )


@app.get("/")
async def root():
    logger = fapilog.get_logger()
    logger.info("hello loki", component="demo")
    return {"status": "ok"}
