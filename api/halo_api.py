"""
Halo Public Safety Integration API
Endpoints for incident analysis, media processing, and threat intelligence
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from pydantic import BaseModel, constr, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
import base64

from services.model_manager import get_model_manager
from api.rate_limits import limiter, get_rate_limit

router = APIRouter()


class IncidentSubmission(BaseModel):
    """Incident submission from Halo app"""
    incident_type: constr(max_length=100)
    description: constr(max_length=5000)
    location: Dict[str, float]  # {"lat": ..., "lon": ...}
    timestamp: datetime
    user_id: constr(max_length=100)
    severity: Optional[int] = None  # 1-5, will be auto-classified if not provided
    media_urls: Optional[List[str]] = []

    @validator('severity')
    def validate_severity(cls, v):
        if v is not None and (v < 1 or v > 5):
            raise ValueError('Severity must be between 1 and 5')
        return v


class ThreatAnalysisRequest(BaseModel):
    """Request for threat analysis"""
    text: Optional[str] = None
    image_url: Optional[str] = None
    audio_url: Optional[str] = None
    video_url: Optional[str] = None
    location: Optional[Dict[str, float]] = None
    context: Optional[Dict[str, Any]] = None


class ThreatAnalysisResponse(BaseModel):
    """Unified threat analysis result"""
    threat_detected: bool
    threat_category: str  # maps to Halo incident types
    confidence: float
    severity: int  # 1-5
    recommendations: List[str]
    detailed_analysis: Dict[str, Any]
    processing_time_ms: int


class IncidentClassificationResponse(BaseModel):
    """Incident classification for Halo"""
    incident_id: str
    incident_type: constr(max_length=100)
    severity: int
    confidence: float
    threat_level: str  # "low", "medium", "high", "critical"
    recommended_actions: List[str]
    emergency_services_needed: bool
    estimated_response_time_min: Optional[int]


@router.post("/halo/analyze", response_model=ThreatAnalysisResponse)
@limiter.limit(get_rate_limit("halo"))
async def analyze_threat(request: ThreatAnalysisRequest):
    """
    Unified threat analysis endpoint for Halo

    **Analyzes:**
    - Text descriptions (threat classifier)
    - Images/video (visual detector)
    - Audio (audio classifier)
    - Multi-modal combinations

    **Uses shared models** - same models as SAIT and Frontline
    **Product-specific** - returns Halo incident types and severity
    """
    import time
    start = time.time()

    try:
        # Get shared model manager (same models as SAIT/Frontline)
        manager = await get_model_manager()

        results = {
            "text_analysis": None,
            "visual_analysis": None,
            "audio_analysis": None
        }

        # Analyze text if provided
        if request.text:
            threat_classifier = manager.threat_classifier
            text_result = await threat_classifier.classify_text(
                description=request.text,
                context=request.context or {}
            )
            results["text_analysis"] = text_result

        # Analyze image if provided
        if request.image_url:
            visual_detector = manager.visual_detector
            # TODO: Download image from URL and analyze
            # For now, placeholder
            results["visual_analysis"] = {"status": "pending", "url": request.image_url}

        # Analyze audio if provided
        if request.audio_url:
            audio_classifier = manager.audio_classifier
            # TODO: Download audio from URL and analyze
            # For now, placeholder
            results["audio_analysis"] = {"status": "pending", "url": request.audio_url}

        # Combine results and map to Halo incident types
        final_threat = _combine_analysis_results(results)

        processing_time = int((time.time() - start) * 1000)

        return ThreatAnalysisResponse(
            threat_detected=final_threat["detected"],
            threat_category=final_threat["category"],
            confidence=final_threat["confidence"],
            severity=final_threat["severity"],
            recommendations=final_threat["recommendations"],
            detailed_analysis=results,
            processing_time_ms=processing_time
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/halo/classify-incident", response_model=IncidentClassificationResponse)
@limiter.limit(get_rate_limit("halo"))
async def classify_incident(request: Request, incident: IncidentSubmission):
    """
    Classify Halo incident and provide recommendations

    **Flow:**
    1. Halo user submits incident
    2. Atlas classifies using shared threat classifier
    3. Returns Halo-specific incident type and severity
    4. Provides recommended actions
    """
    import time
    import uuid
    start = time.time()

    try:
        # Get shared model manager
        manager = await get_model_manager()
        classifier = manager.threat_classifier

        # Classify threat using shared model
        classification = await classifier.classify_text(
            description=incident.description,
            context={"location": incident.location, "incident_type": incident.incident_type}
        )

        # Map to Halo incident types
        halo_mapping = _map_to_halo_incident_type(classification)

        incident_id = str(uuid.uuid4())

        return IncidentClassificationResponse(
            incident_id=incident_id,
            incident_type=halo_mapping["incident_type"],
            severity=halo_mapping["severity"],
            confidence=classification["confidence"],
            threat_level=halo_mapping["threat_level"],
            recommended_actions=halo_mapping["actions"],
            emergency_services_needed=halo_mapping["severity"] >= 4,
            estimated_response_time_min=halo_mapping.get("response_time")
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")


@router.post("/halo/media/analyze")
@limiter.limit(get_rate_limit("halo"))
async def analyze_media(request: Request, file: UploadFile = File(...)):
    """
    Analyze uploaded media (image, video, or audio) from Halo

    **Automatically detects media type and routes to appropriate model**
    - Images/Video → Visual Detector (shared with Frontline)
    - Audio → Audio Classifier (shared with SAIT)
    """
    import time
    start = time.time()

    try:
        # Get shared model manager
        manager = await get_model_manager()

        # Detect media type
        content_type = file.content_type

        if content_type.startswith("image/"):
            # Use shared visual detector
            detector = manager.visual_detector
            # TODO: Process image
            result = {"type": "image", "status": "pending"}

        elif content_type.startswith("audio/"):
            # Use shared audio classifier
            classifier = manager.audio_classifier
            # TODO: Process audio
            result = {"type": "audio", "status": "pending"}

        elif content_type.startswith("video/"):
            # Use shared visual detector
            detector = manager.visual_detector
            # TODO: Process video
            result = {"type": "video", "status": "pending"}

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported media type: {content_type}")

        processing_time = int((time.time() - start) * 1000)
        result["processing_time_ms"] = processing_time

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Media analysis failed: {str(e)}")


@router.get("/halo/intelligence/nearby")
@limiter.limit(get_rate_limit("halo"))
async def get_nearby_intelligence(request: Request, 
    lat: float,
    lon: float,
    radius_km: float = 5.0,
    threat_types: Optional[List[str]] = None
):
    """
    Get threat intelligence near location

    **Cross-product intelligence:**
    - SAIT device detections in area
    - Frontline security alerts nearby
    - Other Halo incidents in proximity

    **Unified view** from central intelligence database
    """
    try:
        # TODO: Query intelligence_patterns table
        # For now, placeholder

        return {
            "location": {"lat": lat, "lon": lon},
            "radius_km": radius_km,
            "threats": [],
            "patterns": [],
            "recommendations": [
                "Cross-product intelligence correlation coming soon"
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Intelligence query failed: {str(e)}")


def _combine_analysis_results(results: Dict[str, Any]) -> Dict[str, Any]:
    """Combine multi-modal analysis results"""
    # Simplified combination logic
    text_result = results.get("text_analysis")

    if text_result:
        return {
            "detected": text_result.get("severity", 1) > 2,
            "category": text_result.get("threat_category", "unknown"),
            "confidence": text_result.get("confidence", 0.0),
            "severity": text_result.get("severity", 1),
            "recommendations": text_result.get("recommendations", [])
        }

    return {
        "detected": False,
        "category": "unknown",
        "confidence": 0.0,
        "severity": 1,
        "recommendations": ["Insufficient data for analysis"]
    }


def _map_to_halo_incident_type(classification: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map unified threat category to Halo incident types

    Uses threat taxonomy mapping:
    - Atlas categories → Halo incident types
    """

    # Halo incident type mapping
    HALO_MAPPING = {
        "violence": {
            "incident_type": "assault",
            "severity": 4,
            "threat_level": "high",
            "actions": ["Call 911", "Evacuate area", "Document evidence"],
            "response_time": 5
        },
        "weapons": {
            "incident_type": "weapons_threat",
            "severity": 5,
            "threat_level": "critical",
            "actions": ["CALL 911 IMMEDIATELY", "Take cover", "Alert others"],
            "response_time": 3
        },
        "suspicious_activity": {
            "incident_type": "suspicious_person",
            "severity": 2,
            "threat_level": "medium",
            "actions": ["Monitor situation", "Report to security", "Stay vigilant"],
            "response_time": 15
        },
        "disturbance": {
            "incident_type": "noise_complaint",
            "severity": 1,
            "threat_level": "low",
            "actions": ["Document incident", "Contact non-emergency line"],
            "response_time": 30
        }
    }

    category = classification.get("category", "unknown")

    return HALO_MAPPING.get(
        category,
        {
            "incident_type": "other",
            "severity": 1,
            "threat_level": "low",
            "actions": ["Document and report"],
            "response_time": None
        }
    )
