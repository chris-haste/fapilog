"""Minimal FastAPI app logging to CloudWatch via LocalStack."""

import os

from fastapi import FastAPI

import fapilog

app = FastAPI()


@app.on_event("startup")
async def setup_logging() -> None:
    os.environ.setdefault("FAPILOG_CORE__SINKS", '["cloudwatch"]')
    os.environ.setdefault("FAPILOG_CLOUDWATCH__ENDPOINT_URL", "http://localhost:4566")
    os.environ.setdefault("FAPILOG_CLOUDWATCH__LOG_GROUP_NAME", "/example/fastapi")
    os.environ.setdefault("FAPILOG_CLOUDWATCH__LOG_STREAM_NAME", "local")


@app.get("/")
async def root():
    logger = fapilog.get_logger()
    logger.info("Request received", path="/")
    return {"status": "ok"}
