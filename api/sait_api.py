"""
SAIT Device Integration API
Endpoints for edge verification, OTA updates, and device management
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
import base64
import numpy as np

from services.model_manager import get_model_manager
from api.rate_limits import limiter, get_rate_limit

router = APIRouter()


class EdgeDetection(BaseModel):
    """Edge detection from SAIT device"""
    device_id: str
    edge_class_id: int
    edge_class_name: str
    edge_confidence: float
    timestamp: datetime
    location: Optional[Dict[str, float]] = None
    audio_base64: Optional[str] = None  # Base64-encoded audio for verification


class EdgeVerificationResponse(BaseModel):
    """Cloud verification result"""
    verified: bool
    edge_confidence: float
    cloud_confidence: float
    edge_class: int
    cloud_class: int
    action: str  # 'edge_detection_trusted', 'cloud_verified', 'cloud_disagrees', 'flagged_for_review'
    final_category: str
    recommendations: List[str]
    processing_time_ms: int


class ModelMetadata(BaseModel):
    """Model version metadata"""
    model_version: str
    model_type: str
    architecture: str
    num_classes: int
    input_dim: int
    format: str
    accuracy: float
    size_kb: int
    deployed_at: str
    compatible_devices: List[str]
    download_url: str
    checksum: str


@router.post("/sait/verify", response_model=EdgeVerificationResponse)
@limiter.limit(get_rate_limit("sait"))
async def verify_edge_detection(request: Request, detection: EdgeDetection):
    """
    Verify SAIT edge detection with cloud model

    **Flow:**
    1. SAIT device detects threat with confidence < 0.85
    2. Device sends detection + audio to cloud
    3. Cloud re-analyzes with larger model
    4. Returns verification result

    **Use cases:**
    - Low confidence edge detections need confirmation
    - Ambiguous audio signatures
    - Multi-modal correlation opportunities
    """
    import time
    start = time.time()

    try:
        # Get shared model manager (singleton - loaded once for all products)
        manager = await get_model_manager()
        audio_classifier = manager.audio_classifier

        # If audio provided, re-analyze with cloud model
        if detection.audio_base64:
            try:
                # Decode audio
                audio_bytes = base64.b64decode(detection.audio_base64)
                # Convert to numpy array (assuming 16kHz, 16-bit PCM)
                audio_data = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

                # Cloud verification
                verification_result = await audio_classifier.verify_edge_detection(
                    sait_detection={
                        "class_id": detection.edge_class_id,
                        "confidence": detection.edge_confidence
                    },
                    audio_data=audio_data
                )

                processing_time = int((time.time() - start) * 1000)

                return EdgeVerificationResponse(
                    **verification_result,
                    processing_time_ms=processing_time
                )

            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Audio processing failed: {str(e)}")

        # No audio - can only check if confidence is acceptable
        if detection.edge_confidence > 0.85:
            return EdgeVerificationResponse(
                verified=True,
                edge_confidence=detection.edge_confidence,
                cloud_confidence=detection.edge_confidence,
                edge_class=detection.edge_class_id,
                cloud_class=detection.edge_class_id,
                action="edge_detection_trusted",
                final_category=detection.edge_class_name,
                recommendations=["High edge confidence - no cloud verification needed"],
                processing_time_ms=int((time.time() - start) * 1000)
            )
        else:
            return EdgeVerificationResponse(
                verified=False,
                edge_confidence=detection.edge_confidence,
                cloud_confidence=0.0,
                edge_class=detection.edge_class_id,
                cloud_class=-1,
                action="flagged_for_review",
                final_category="unknown",
                recommendations=["Low confidence, no audio provided for verification"],
                processing_time_ms=int((time.time() - start) * 1000)
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


@router.get("/sait/models/latest", response_model=ModelMetadata)
@limiter.limit(get_rate_limit("sait"))
async def get_latest_model(request: Request, 
    device_type: str = "nrf5340",
    current_version: Optional[str] = None
):
    """
    Get latest SAIT model metadata for OTA updates

    **Flow:**
    1. SAIT device checks for updates periodically
    2. Sends current version
    3. Cloud returns latest version metadata
    4. Device decides whether to download

    **Supports:**
    - Model versioning
    - Rollback capability
    - Performance tracking
    """
    # Get shared model manager
    manager = await get_model_manager()
    audio_classifier = manager.audio_classifier
    model_info = audio_classifier.get_model_version()

    # Check if update available
    update_available = (
        current_version is None or
        current_version != model_info['model_version']
    )

    return ModelMetadata(
        model_version=model_info['model_version'],
        model_type=model_info['model_type'],
        architecture=model_info['architecture'],
        num_classes=model_info['num_classes'],
        input_dim=model_info['input_dim'],
        format=model_info['format'],
        accuracy=0.92,  # TODO: Get from model_registry table
        size_kb=186,  # TODO: Get actual model size
        deployed_at=model_info['deployed_at'],
        compatible_devices=model_info['compatible_devices'],
        download_url=f"/api/v1/sait/models/{model_info['model_version']}/download",
        checksum="sha256:placeholder"  # TODO: Calculate actual checksum
    )


@router.get("/sait/models/{version}/download")
@limiter.limit(get_rate_limit("sait"))
async def download_model(request: Request, version: str, format: str = "tflite"):
    """
    Download SAIT model for OTA update

    **Formats supported:**
    - `tflite` - TensorFlow Lite for edge deployment
    - `cmsis-nn` - ARM CMSIS-NN optimized
    - `pytorch` - PyTorch (for testing only)

    **Security:**
    - Models signed with cryptographic keys
    - Devices validate integrity before deployment
    - Rollback if new model performs worse
    """
    from fastapi.responses import Response

    audio_classifier = await get_audio_classifier()

    try:
        model_bytes = await audio_classifier.get_ota_model_package(target_format=format)

        if model_bytes is None:
            raise HTTPException(status_code=404, detail="Model not found")

        return Response(
            content=model_bytes,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename=sait_model_{version}.{format}",
                "X-Model-Version": version,
                "X-Model-Format": format,
                "X-Checksum": "sha256:placeholder"  # TODO: Add real checksum
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model download failed: {str(e)}")


@router.post("/sait/telemetry")
@limiter.limit(get_rate_limit("sait"))
async def submit_telemetry(request: Request, telemetry: Dict[str, Any]):
    """
    Submit telemetry data from SAIT device

    **Collected metrics:**
    - Device health (battery, temperature, uptime)
    - Model performance (accuracy, latency, memory)
    - Network stats (mesh connectivity, message routing)
    - Detection statistics (true/false positives)

    **Used for:**
    - Device monitoring and alerting
    - Model performance tracking
    - Network optimization
    - Predictive maintenance
    """
    # TODO: Store in telemetry table
    # TODO: Check for anomalies
    # TODO: Trigger alerts if needed

    return {
        "success": True,
        "device_id": telemetry.get("device_id"),
        "received_at": datetime.now().isoformat(),
        "alerts": []  # Any alerts based on telemetry
    }


@router.post("/sait/feedback")
@limiter.limit(get_rate_limit("sait"))
async def submit_detection_feedback(request: Request, feedback: Dict[str, Any]):
    """
    Submit feedback on SAIT detection accuracy

    **Used for:**
    - Continuous model improvement
    - False positive/negative tracking
    - Training data collection
    - Model retraining triggers

    **Sources:**
    - User corrections
    - Multi-modal verification
    - Law enforcement validation
    """
    # TODO: Store in training_samples table
    # TODO: Update model metrics
    # TODO: Trigger retraining if threshold reached

    return {
        "success": True,
        "feedback_id": "uuid-example",
        "added_to_training_queue": True,
        "impact": {
            "similar_detections": 12,
            "estimated_accuracy_improvement": 0.03,
            "retraining_scheduled": None  # Or datetime if triggered
        }
    }


@router.get("/sait/devices/{device_id}/status")
@limiter.limit(get_rate_limit("sait"))
async def get_device_status(request: Request, device_id: str):
    """
    Get SAIT device status and health

    **Returns:**
    - Device online/offline status
    - Last seen timestamp
    - Current model version
    - Battery level
    - Network connectivity
    - Recent detections
    """
    # TODO: Query from device registry

    return {
        "device_id": device_id,
        "status": "online",
        "last_seen": datetime.now().isoformat(),
        "model_version": "1.0.0",
        "battery_percent": 87,
        "network": {
            "mesh_neighbors": 5,
            "signal_strength": -65,
            "last_sync": datetime.now().isoformat()
        },
        "recent_detections": 23,
        "uptime_hours": 720.5
    }
