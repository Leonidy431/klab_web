"""
K-Laboratory Backend Application.

FastAPI application with BlueOS integration,
e-commerce shop, and community forum.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from loguru import logger

from app.api.v1 import router as api_v1_router
from app.core.config import settings
from app.core.database import close_db, init_db
from app.modules.blueos import BlueOSClient, get_blueos_client
from app.modules.blueos.telemetry import get_telemetry_service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    logger.info("Starting K-Laboratory Backend...")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Initialize BlueOS client
    try:
        blueos = await get_blueos_client()
        if await blueos.health_check():
            logger.info("BlueOS connected")

            # Start telemetry service
            telemetry = await get_telemetry_service()
            await telemetry.start(blueos_client=blueos)
            logger.info("Telemetry service started")
        else:
            logger.warning("BlueOS not available - running in offline mode")
    except Exception as e:
        logger.warning(f"BlueOS initialization failed: {e}")

    logger.info("K-Laboratory Backend started successfully")

    yield

    # Shutdown
    logger.info("Shutting down K-Laboratory Backend...")

    # Stop telemetry
    telemetry = await get_telemetry_service()
    await telemetry.stop()

    # Close database
    await close_db()

    logger.info("Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
    K-Laboratory Backend Platform

    ## Features

    - **BlueOS Integration**: Real-time ROV control and telemetry
    - **Shop**: E-commerce for ROV parts and equipment
    - **Forum**: Community discussions
    - **API**: RESTful API with OpenAPI documentation

    ## Documentation

    - [API Docs](/docs) - Interactive Swagger UI
    - [ReDoc](/redoc) - Alternative documentation
    """,
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_v1_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["System"])
async def health_check() -> dict:
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "version": settings.app_version,
    }


@app.get("/", tags=["System"])
async def root() -> dict:
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "api": settings.api_v1_prefix,
    }
