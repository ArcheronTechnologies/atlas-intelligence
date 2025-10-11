"""
Threat Classification & Inference API
"""

import logging
import time
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

from api.rate_limits import limiter, get_rate_limit

router = APIRouter()
logger = logging.getLogger(__name__)


class ThreatClassificationRequest(BaseModel):
    """Request for threat classification"""
    type: str = Field(..., description="Type: text, visual, audio, or multi_modal")
    data: str = Field(..., description="Text description or media URL")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Contextual information")
    options: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ThreatClassificationResponse(BaseModel):
    """Response for threat classification"""
    classification: Dict[str, Any]
    product_mappings: Dict[str, Any]
    nearby_patterns: List[Dict[str, Any]] = []
    recommendations: List[str] = []
    processing_time_ms: int


@router.post("/classify/threat", response_model=ThreatClassificationResponse)
@limiter.limit(get_rate_limit("classify"))
async def classify_threat(request: Request, classification_request: ThreatClassificationRequest):
    """
    Classify a threat using multi-modal AI analysis

    **Supports:**
    - Text descriptions
    - Visual data (images/video)
    - Audio data
    - Multi-modal combinations

    **Returns unified classification** across all products (Halo, Frontline, SAIT)
    """
    from services.threat_classifier import get_threat_classifier

    start_time = time.time()

    try:
        classifier = await get_threat_classifier()

        # Classify based on type
        if classification_request.type == "text":
            result = await classifier.classify_text(classification_request.data, classification_request.context)
        else:
            # For visual/audio, return placeholder for now
            result = {
                "threat_category": "suspicious_activity",
                "threat_subcategory": "unknown",
                "severity": 2,
                "confidence": 0.5,
                "product_mappings": {
                    "halo_incident_type": "suspicious_activity",
                    "polisen_type": "Annan händelse",
                    "frontline_objects": [],
                    "sait_threat_level": "low"
                }
            }

        processing_time = int((time.time() - start_time) * 1000)

        # TODO: Query nearby patterns from database
        nearby_patterns = []

        # Generate recommendations
        recommendations = []
        if result["severity"] >= 4:
            recommendations.append("Immediate response recommended")
            recommendations.append("Alert nearby Halo users")
        elif result["severity"] >= 3:
            recommendations.append("Monitor situation closely")

        return ThreatClassificationResponse(
            classification={
                "threat_category": result["threat_category"],
                "threat_subcategory": result["threat_subcategory"],
                "severity": result["severity"],
                "confidence": result["confidence"]
            },
            product_mappings=result["product_mappings"],
            nearby_patterns=nearby_patterns,
            recommendations=recommendations,
            processing_time_ms=processing_time
        )

    except Exception as e:
        logger.error(f"Error in classify_threat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/active")
@limiter.limit(get_rate_limit("models"))
async def get_active_models(request: Request):
    """Get currently active models"""
    # TODO: Query model_registry table
    return {
        "threat_classifier": {
            "version": "v1.0.0",
            "accuracy": 0.87,
            "last_updated": datetime.now().isoformat()
        },
        "visual_detector": {
            "version": "yolov8n-v2.1.0",
            "accuracy": 0.92,
            "last_updated": datetime.now().isoformat()
        },
        "audio_classifier": {
            "version": "sait-cloud-v1.2.0",
            "accuracy": 0.89,
            "last_updated": datetime.now().isoformat()
        }
    }
