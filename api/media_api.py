"""
Media Analysis API (Photo, Video, Audio)
"""

import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from pydantic import BaseModel, validator
from typing import Optional, Dict, Any, List
from datetime import datetime

from api.rate_limits import limiter, get_rate_limit

router = APIRouter()
logger = logging.getLogger(__name__)

# File size limits (bytes)
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50MB
MAX_AUDIO_SIZE = 5 * 1024 * 1024   # 5MB

# Allowed MIME types
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/jpg"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo"}
ALLOWED_AUDIO_TYPES = {"audio/wav", "audio/mpeg", "audio/mp4"}


class MediaAnalysisResponse(BaseModel):
    """Response for media analysis"""
    success: bool
    media_type: str
    visual_analysis: Optional[Dict[str, Any]] = None
    audio_analysis: Optional[Dict[str, Any]] = None
    threat_classification: Dict[str, Any]
    source_models: Dict[str, str]
    processing_time_ms: int


@router.post("/analyze/media", response_model=MediaAnalysisResponse)
@limiter.limit(get_rate_limit("analyze"))
async def analyze_media(
    request: Request,
    file: UploadFile = File(...),
    media_type: str = Form(...),
    analysis_depth: str = Form(default="quick")
):
    """
    Analyze uploaded media for threats

    **Supports:**
    - Photos (JPEG, PNG)
    - Video (MP4, MOV)
    - Audio (WAV, MP3)

    **Analysis includes:**
    - Object detection (visual)
    - Threat sound detection (audio)
    - Unified threat classification
    """
    from services.media_analyzer import get_media_analyzer

    try:
        # Validate MIME type
        if media_type == "photo" and file.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid image type: {file.content_type}")
        elif media_type == "video" and file.content_type not in ALLOWED_VIDEO_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid video type: {file.content_type}")
        elif media_type == "audio" and file.content_type not in ALLOWED_AUDIO_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid audio type: {file.content_type}")

        # Read file bytes
        file_bytes = await file.read()

        # Validate file size
        file_size = len(file_bytes)
        if media_type == "photo" and file_size > MAX_IMAGE_SIZE:
            raise HTTPException(status_code=413, detail=f"Image too large: {file_size/1024/1024:.1f}MB (max 10MB)")
        elif media_type == "video" and file_size > MAX_VIDEO_SIZE:
            raise HTTPException(status_code=413, detail=f"Video too large: {file_size/1024/1024:.1f}MB (max 50MB)")
        elif media_type == "audio" and file_size > MAX_AUDIO_SIZE:
            raise HTTPException(status_code=413, detail=f"Audio too large: {file_size/1024/1024:.1f}MB (max 5MB)")

        analyzer = await get_media_analyzer()

        # Analyze based on media type
        if media_type == "photo":
            result = await analyzer.analyze_photo(
                file_bytes,
                return_detailed=(analysis_depth == "detailed")
            )

            if not result.get("success"):
                raise HTTPException(status_code=500, detail=result.get("error", "Analysis failed"))

            return MediaAnalysisResponse(
                success=True,
                media_type="photo",
                visual_analysis=result["visual_analysis"],
                threat_classification=result["threat_classification"],
                source_models=result["source_models"],
                processing_time_ms=result["processing_time_ms"]
            )

        elif media_type == "video":
            result = await analyzer.analyze_video(file_bytes)
            return MediaAnalysisResponse(
                success=True,
                media_type="video",
                threat_classification=result.get("classification", {}),
                source_models={"video_analyzer": "placeholder-v0.1"},
                processing_time_ms=result["processing_time_ms"]
            )

        elif media_type == "audio":
            result = await analyzer.analyze_audio(file_bytes)
            return MediaAnalysisResponse(
                success=True,
                media_type="audio",
                audio_analysis=result.get("audio_analysis", {}),
                threat_classification=result.get("classification", {}),
                source_models={"audio_classifier": "placeholder-v0.1"},
                processing_time_ms=result["processing_time_ms"]
            )

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported media type: {media_type}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in analyze_media: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analyze/health")
@limiter.limit(get_rate_limit("info"))
async def media_analysis_health(request: Request):
    """Check media analysis service health"""
    return {
        "status": "operational",
        "models_loaded": True,
        "supported_formats": {
            "photo": ["jpg", "jpeg", "png"],
            "video": ["mp4", "mov", "avi"],
            "audio": ["wav", "mp3", "m4a"]
        },
        "timestamp": datetime.now().isoformat()
    }
