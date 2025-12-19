"""FastAPI example demonstrating async logger usage with dependency injection.

This example shows how to use the new AsyncLoggerFacade with FastAPI,
including proper lifecycle management and context binding.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from fapilog import get_async_logger, runtime_async

# Global logger for application-level events
app_logger = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for logger setup and cleanup."""
    global app_logger

    # Initialize application logger
    app_logger = await get_async_logger("fastapi_app")
    await app_logger.info("Application starting up")

    yield

    # Cleanup
    if app_logger:
        await app_logger.info("Application shutting down")
        await app_logger.drain()


# Create FastAPI app with lifespan management
app = FastAPI(
    title="FastAPI Async Logging Example",
    description="Demonstrates async logger integration with FastAPI",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_request_logger(request: Request) -> Any:
    """Dependency to provide a request-scoped logger with bound context."""
    # Create logger for this request
    logger = await get_async_logger("request")

    # Bind request context
    bound_logger = logger.bind(
        request_id=request.headers.get("X-Request-ID", "unknown"),
        user_agent=request.headers.get("User-Agent", "unknown"),
        method=request.method,
        path=request.url.path,
        client_ip=request.client.host if request.client else "unknown",
    )

    return bound_logger


@app.get("/")
async def root(logger: Any = Depends(get_request_logger)):
    """Root endpoint demonstrating basic logging."""
    await logger.info("Root endpoint accessed")
    return {"message": "Hello World", "status": "success"}


@app.get("/users/{user_id}")
async def get_user(user_id: int, logger: Any = Depends(get_request_logger)):
    """User endpoint demonstrating structured logging."""
    await logger.info("User lookup requested", user_id=user_id, operation="get_user")

    # Simulate user lookup
    if user_id <= 0:
        await logger.warning(
            "Invalid user ID provided", user_id=user_id, reason="non_positive_id"
        )
        raise HTTPException(status_code=400, detail="Invalid user ID")

    if user_id > 1000:
        await logger.error("User not found", user_id=user_id, reason="user_not_found")
        raise HTTPException(status_code=404, detail="User not found")

    await logger.info(
        "User found successfully",
        user_id=user_id,
        operation="get_user",
        result="success",
    )

    return {
        "user_id": user_id,
        "name": f"User {user_id}",
        "email": f"user{user_id}@example.com",
    }


@app.post("/users")
async def create_user(
    user_data: dict[str, Any], logger: Any = Depends(get_request_logger)
):
    """User creation endpoint demonstrating error logging."""
    await logger.info(
        "User creation requested",
        operation="create_user",
        user_data_keys=list(user_data.keys()),
    )

    try:
        # Simulate user creation
        if "email" not in user_data:
            raise ValueError("Email is required")

        if "name" not in user_data:
            raise ValueError("Name is required")

        # Simulate successful creation
        new_user_id = 1001  # In real app, this would be generated

        await logger.info(
            "User created successfully",
            operation="create_user",
            new_user_id=new_user_id,
            result="success",
        )

        return {"user_id": new_user_id, "message": "User created successfully"}

    except ValueError as e:
        await logger.error(
            "User creation failed - validation error",
            operation="create_user",
            error=str(e),
            user_data=user_data,
        )
        raise HTTPException(status_code=400, detail=str(e)) from e

    except Exception:
        await logger.exception(
            "User creation failed - unexpected error",
            operation="create_user",
            user_data=user_data,
        )
        raise HTTPException(status_code=500, detail="Internal server error") from None


@app.get("/health")
async def health_check(logger: Any = Depends(get_request_logger)):
    """Health check endpoint."""
    await logger.debug("Health check requested")
    return {"status": "healthy", "timestamp": "2025-01-20T12:00:00Z"}


@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request, exc: Exception, logger: Any = Depends(get_request_logger)
):
    """Global exception handler with logging."""
    await logger.exception(
        "Unhandled exception occurred",
        exception_type=type(exc).__name__,
        exception_message=str(exc),
        path=request.url.path,
        method=request.method,
    )

    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Example of using runtime_async context manager
@app.get("/batch-operation")
async def batch_operation(logger: Any = Depends(get_request_logger)):
    """Example of using runtime_async for batch operations."""
    await logger.info("Starting batch operation")

    # Use runtime_async for a batch of operations
    async with runtime_async() as batch_logger:
        await batch_logger.info("Batch operation started")

        # Simulate batch processing
        for i in range(5):
            await batch_logger.info(f"Processing item {i}", item_id=i)
            await asyncio.sleep(0.1)  # Simulate work

        await batch_logger.info("Batch operation completed")

    # runtime_async automatically drains the logger
    await logger.info("Batch operation finished")

    return {"message": "Batch operation completed", "items_processed": 5}


if __name__ == "__main__":
    import uvicorn

    # Run the application
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
