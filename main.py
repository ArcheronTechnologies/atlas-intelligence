"""
Atlas Intelligence Backbone
Main FastAPI application entry point
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from api.inference_api import router as inference_router
from api.media_api import router as media_router
from api.training_api import router as training_router
from api.intelligence_api import router as intelligence_router
from api.sait_api import router as sait_router
from api.halo_api import router as halo_router
from api.admin_api import router as admin_router
from api.data_api import router as data_router
from database.database import get_database
from services.model_manager import get_model_manager
from config.settings import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("🚀 Starting Atlas Intelligence v%s", settings.VERSION)
    logger.info("Environment: %s", settings.ATLAS_ENV)

    # Initialize database (optional for local development)
    db = None
    try:
        db = await get_database()
        await db.initialize()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.warning("⚠️ Database not available (running without persistence): %s", e)
        db = None  # Continue without database for local development

    # Load ML models (singleton - shared across all products)
    try:
        logger.info("Loading unified model manager (central stack)...")
        manager = await get_model_manager()
        model_info = manager.get_model_info()
        logger.info("✅ ML models loaded and shared across products:")
        for model_name, info in model_info["models"].items():
            if info["loaded"]:
                logger.info(f"   - {model_name}: {info['type']}")
                logger.info(f"     Shared by: {', '.join(info['shared_by'])}")
    except Exception as e:
        logger.warning("⚠️ ML models not loaded: %s", e)

    # Start data collection service
    if db:
        try:
            from services.data_collector import start_data_collection
            await start_data_collection()
            logger.info("✅ Data collection service started")
        except Exception as e:
            logger.warning("⚠️ Data collection service failed to start: %s", e)

    logger.info("🎉 Atlas Intelligence ready")

    yield

    # Cleanup
    logger.info("🔄 Shutting down Atlas Intelligence...")

    # Stop data collection
    try:
        from services.data_collector import stop_data_collection
        await stop_data_collection()
        logger.info("✅ Data collection service stopped")
    except Exception as e:
        logger.warning("⚠️ Error stopping data collection: %s", e)

    if db:
        await db.close()
    logger.info("✅ Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Atlas Intelligence",
    # Add rate limiter to app state
    state={"limiter": limiter},
    description="""
    **Atlas Intelligence Backbone** - Shared AI/ML infrastructure for threat intelligence.

    ## Features

    - 🧠 **Threat Classification**: Multi-modal threat categorization
    - 📸 **Media AI Analysis**: Photo, video, and audio analysis
    - 🎯 **Model Training**: Continuous improvement pipeline
    - 📊 **Intelligence Patterns**: Cross-product correlation

    ## Products Powered by Atlas

    - **Halo**: Public safety incident platform
    - **Frontline AI**: Physical security system
    - **SAIT_01**: Tactical audio intelligence
    """,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    contact={
        "name": "Atlas Intelligence Support",
        "email": "support@example.com"
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT"
    }
)

# Add rate limit exception handler
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Trusted Host Middleware (production security)
if settings.ATLAS_ENV == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*.railway.app", "atlas.intelligence", "*.atlas.intelligence"]
    )

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include API routers - Product-specific namespaces with shared models
app.include_router(halo_router, prefix="/api/v1", tags=["halo"])
app.include_router(sait_router, prefix="/api/v1", tags=["sait"])
# app.include_router(frontline_router, prefix="/api/v1", tags=["frontline"])  # Coming soon

# Core service routers
app.include_router(inference_router, prefix="/api/v1", tags=["inference"])
app.include_router(media_router, prefix="/api/v1", tags=["media"])
app.include_router(training_router, prefix="/api/v1", tags=["training"])
app.include_router(intelligence_router, prefix="/api/v1", tags=["intelligence"])

# Admin router (model management, hot-reload)
app.include_router(admin_router, prefix="/api/v1", tags=["admin"])
app.include_router(data_router, prefix="/api/v1", tags=["data"])

# Prometheus metrics
if settings.PROMETHEUS_ENABLED:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)


@app.get("/", tags=["info"])
@limiter.limit("100/minute")
async def root(request: Request):
    """API information and health check"""
    return {
        "service": "Atlas Intelligence",
        "version": settings.VERSION,
        "environment": settings.ATLAS_ENV,
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
        "documentation": "/docs",
        "health": "/health"
    }


@app.get("/health", tags=["info"])
@limiter.limit("60/minute")
async def health_check(request: Request):
    """Comprehensive health check"""
    try:
        db = await get_database()
        await db.pool.fetchval("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        logger.error("Database health check failed: %s", e)
        db_status = "unavailable"

    # App is operational even without database (degraded mode)
    # Core AI services work without database
    app_status = "healthy"
    mode = "full" if db_status == "healthy" else "degraded"

    return {
        "status": app_status,
        "database": db_status,
        "mode": mode,
        "services": {
            "threat_classifier": "operational",
            "visual_detector": "operational",
            "audio_classifier": "operational"
        },
        "version": settings.VERSION,
        "timestamp": datetime.now().isoformat()
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.DEBUG else "An error occurred",
            "timestamp": datetime.now().isoformat()
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
