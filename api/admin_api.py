"""
Admin API for Atlas Intelligence
Model management, system control, hot-reload

Designed for Railway deployments with minimal code pushes
"""

from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel
from typing import Optional, Dict, List
import logging
import os
import sqlalchemy as sa

from services.model_manager import get_model_manager
from services.model_storage import get_model_storage
from api.rate_limits import limiter, get_rate_limit

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

# Admin authentication (simple token-based)
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "change-me-in-production")


def verify_admin(authorization: str = Header(None)):
    """Verify admin token"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    # Expected format: "Bearer <token>"
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer" or token != ADMIN_TOKEN:
            raise HTTPException(status_code=403, detail="Invalid admin token")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")


class ModelReloadRequest(BaseModel):
    """Model reload request"""
    model_type: str  # 'threat_classifier', 'visual_detector', 'audio_classifier', 'all'
    version: Optional[str] = "latest"
    force_download: bool = False


class ModelReloadResponse(BaseModel):
    """Model reload response"""
    success: bool
    model_type: str
    version: str
    message: str
    reloaded_at: str


class ModelUploadRequest(BaseModel):
    """Model upload notification (after manual S3 upload)"""
    model_name: str
    version: str
    s3_key: str


@router.post("/reload-models", response_model=ModelReloadResponse, dependencies=[])
@limiter.limit("10/minute")
async def reload_models(
    request: Request,
    reload_request: ModelReloadRequest,
    authorization: str = Header(None)
):
    """
    Hot-reload models without redeploying code

    Use cases:
    - After uploading new model to S3
    - After training new version
    - Switching between model versions

    Authentication: Bearer token in Authorization header

    Example:
        curl -X POST https://atlas.railway.app/admin/reload-models \\
          -H "Authorization: Bearer $ADMIN_TOKEN" \\
          -H "Content-Type: application/json" \\
          -d '{"model_type": "visual_detector", "version": "v2.1.0"}'
    """
    verify_admin(authorization)

    try:
        from datetime import datetime

        model_manager = get_model_manager()

        if reload_request.model_type == "all":
            # Reload all models
            logger.info("🔄 Reloading ALL models...")

            # Reload each model
            await model_manager.threat_classifier.load_model()
            await model_manager.visual_detector.initialize()
            await model_manager.audio_classifier.load_model()

            return ModelReloadResponse(
                success=True,
                model_type="all",
                version=reload_request.version,
                message="All models reloaded successfully",
                reloaded_at=datetime.utcnow().isoformat()
            )

        elif reload_request.model_type == "threat_classifier":
            logger.info(f"🔄 Reloading threat classifier (v{reload_request.version})...")
            await model_manager.threat_classifier.load_model()

        elif reload_request.model_type == "visual_detector":
            logger.info(f"🔄 Reloading visual detector (v{reload_request.version})...")
            await model_manager.visual_detector.initialize()

        elif reload_request.model_type == "audio_classifier":
            logger.info(f"🔄 Reloading audio classifier (v{reload_request.version})...")
            await model_manager.audio_classifier.load_model()

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid model_type: {reload_request.model_type}"
            )

        return ModelReloadResponse(
            success=True,
            model_type=reload_request.model_type,
            version=reload_request.version,
            message=f"{reload_request.model_type} reloaded successfully",
            reloaded_at=datetime.utcnow().isoformat()
        )

    except Exception as e:
        logger.error(f"Model reload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Model reload failed: {str(e)}")


@router.post("/collect-now", dependencies=[])
@limiter.limit("20/hour")
async def collect_now(
    request: Request,
    authorization: str = Header(None)
):
    """
    Trigger immediate data collection (one-time)

    Authentication: Bearer token in Authorization header

    Example:
        curl -X POST https://loving-purpose-production.up.railway.app/api/v1/admin/collect-now \\
          -H "Authorization: Bearer $ADMIN_TOKEN"
    """
    verify_admin(authorization)

    try:
        from services.data_collector import PolisenCollector
        from datetime import datetime

        logger.info("🔄 Running immediate data collection...")

        # Create collector and run once
        collector = PolisenCollector()
        result = await collector.collect()

        logger.info(f"✅ Collection completed: {result}")

        return {
            "success": result.get("success", False),
            "records_collected": result.get("records", 0),
            "message": f"Collected {result.get('records', 0)} incidents",
            "completed_at": datetime.utcnow().isoformat(),
            "details": result
        }

    except Exception as e:
        logger.error(f"Collection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Collection failed: {str(e)}")


@router.post("/reset-database", dependencies=[])
@limiter.limit("5/hour")
async def reset_database(
    request: Request,
    authorization: str = Header(None)
):
    """
    Reset database (drop all tables and recreate)

    Authentication: Bearer token in Authorization header

    Example:
        curl -X POST https://loving-purpose-production.up.railway.app/api/v1/admin/reset-database \\
          -H "Authorization: Bearer $ADMIN_TOKEN"
    """
    verify_admin(authorization)

    try:
        from datetime import datetime
        from database.database import get_database
        from database.models import Base

        logger.info("🔄 Resetting database schema...")

        db = await get_database()

        # Drop and recreate all tables
        async with db.engine.begin() as conn:
            # Drop all tables
            logger.info("Dropping all tables...")
            await conn.run_sync(Base.metadata.drop_all)

            # Try to enable PostGIS (will fail gracefully if not available)
            try:
                await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS postgis"))
                logger.info("PostGIS enabled")
            except Exception as e:
                logger.warning(f"PostGIS not available: {e}")

            # Create all tables
            logger.info("Creating all tables...")
            await conn.run_sync(Base.metadata.create_all)

        logger.info("✅ Database reset successfully")

        return {
            "success": True,
            "message": "Database reset successfully - all tables dropped and recreated",
            "completed_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Database reset failed: {e}")
        raise HTTPException(status_code=500, detail=f"Database reset failed: {str(e)}")


@router.get("/models/versions/{model_name}", dependencies=[])
@limiter.limit("20/minute")
async def list_model_versions(
    request: Request,
    model_name: str,
    authorization: str = Header(None)
):
    """
    List all available versions of a model in S3

    Returns versions in descending order (newest first)
    """
    verify_admin(authorization)

    try:
        storage = get_model_storage()
        versions = await storage.list_model_versions(model_name)

        if not versions:
            return {
                "model_name": model_name,
                "versions": [],
                "storage_type": storage.storage_type,
                "message": "No versions found or S3 not configured"
            }

        return {
            "model_name": model_name,
            "versions": versions,
            "storage_type": storage.storage_type,
            "latest": versions[0] if versions else None
        }

    except Exception as e:
        logger.error(f"Failed to list versions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/metadata/{model_name}", dependencies=[])
@limiter.limit("20/minute")
async def get_model_metadata(
    request: Request,
    model_name: str,
    authorization: str = Header(None)
):
    """
    Get model metadata from S3

    Returns version, accuracy, upload date, etc.
    """
    verify_admin(authorization)

    try:
        storage = get_model_storage()
        metadata = await storage.get_model_metadata(model_name)

        if not metadata:
            raise HTTPException(
                status_code=404,
                detail=f"Metadata not found for {model_name}"
            )

        return metadata

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get metadata: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", dependencies=[])
@limiter.limit("60/minute")
async def admin_health(request: Request, authorization: str = Header(None)):
    """Admin health check with detailed system info"""
    verify_admin(authorization)

    try:
        import psutil
        from datetime import datetime

        model_manager = get_model_manager()
        storage = get_model_storage()

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "system": {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent
            },
            "models": {
                "threat_classifier": {
                    "loaded": True,
                    "type": type(model_manager.threat_classifier).__name__
                },
                "visual_detector": {
                    "loaded": model_manager.visual_detector.loaded,
                    "device": model_manager.visual_detector.device
                },
                "audio_classifier": {
                    "loaded": model_manager.audio_classifier.loaded,
                    "device": model_manager.audio_classifier.device
                }
            },
            "storage": {
                "type": storage.storage_type,
                "bucket": storage.s3_bucket if storage.storage_type == "s3" else None,
                "cache_dir": str(storage.local_cache_dir)
            }
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "degraded",
            "error": str(e)
        }


@router.post("/cache/clear", dependencies=[])
@limiter.limit("5/minute")
async def clear_model_cache(request: Request, authorization: str = Header(None)):
    """
    Clear local model cache (forces re-download from S3)

    Use this after uploading a new model with the same version number
    """
    verify_admin(authorization)

    try:
        import shutil

        storage = get_model_storage()
        cache_dir = storage.local_cache_dir

        if cache_dir.exists():
            # Remove all .pt and .pth files
            cleared = []
            for model_file in cache_dir.glob("*.pt"):
                model_file.unlink()
                cleared.append(model_file.name)
            for model_file in cache_dir.glob("*.pth"):
                model_file.unlink()
                cleared.append(model_file.name)

            return {
                "success": True,
                "cleared_files": cleared,
                "message": f"Cleared {len(cleared)} model files from cache"
            }
        else:
            return {
                "success": True,
                "cleared_files": [],
                "message": "Cache directory does not exist"
            }

    except Exception as e:
        logger.error(f"Cache clear failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
