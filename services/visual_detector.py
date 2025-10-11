"""
Visual Detection Service
YOLOv8-based object detection (extracted from Frontline AI)
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import base64
from io import BytesIO
from PIL import Image

# Optional cv2 import for environments without OpenGL
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logging.warning("OpenCV not available. Using PIL for image processing.")

try:
    from ultralytics import YOLO
    import torch
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    logging.warning("YOLOv8 not available. Install ultralytics for full functionality.")

from config.settings import settings
from services.model_storage import get_model_storage

logger = logging.getLogger(__name__)


class VisualDetector:
    """YOLOv8-based visual threat detection"""

    def __init__(self):
        self.model = None
        self.model_path = None
        self.device = "cpu"
        self.loaded = False

        # Detection classes relevant to threats
        self.threat_classes = {
            0: "person",
            1: "bicycle",
            2: "car",
            3: "motorcycle",
            5: "bus",
            7: "truck",
            # COCO dataset IDs - weapon detection requires custom trained model
        }

        # Confidence thresholds
        self.confidence_thresholds = {
            "person": 0.5,
            "car": 0.5,
            "truck": 0.5,
            "motorcycle": 0.5,
            "weapon": 0.3  # Custom class if available
        }

    async def initialize(self):
        """Load YOLOv8 model (from S3 if configured, else local/download)"""
        if not YOLO_AVAILABLE:
            logger.warning("⚠️ YOLOv8 not available - using mock detection")
            return False

        try:
            # Use YOLOv8m (medium) for better accuracy vs YOLOv8n (nano)
            # Trade-off: ~25MB model, ~2x slower, but +5-10% accuracy
            model_name = "yolov8m.pt"  # Medium model for production

            # Try to get model from storage (S3 or local cache)
            storage = get_model_storage()
            model_path = await storage.get_model(model_name, version="latest")

            # Fallback: Check Frontline location (local dev)
            if not model_path:
                frontline_model_m = Path("/Users/timothyaikenhead/Desktop/Frontline AI/atlas-mvp/backend/yolov8m.pt")
                frontline_model_n = Path("/Users/timothyaikenhead/Desktop/Frontline AI/atlas-mvp/backend/yolov8n.pt")

                if frontline_model_m.exists():
                    logger.info(f"Found YOLOv8m model at Frontline location")
                    model_path = frontline_model_m
                elif frontline_model_n.exists():
                    logger.info(f"Found YOLOv8n model at Frontline location")
                    model_path = frontline_model_n

            # Fallback: Download from ultralytics
            if not model_path or not model_path.exists():
                logger.info("📥 Downloading YOLOv8m model from ultralytics...")
                model_path = Path(model_name)  # YOLO will auto-download

            self.model = YOLO(str(model_path))
            self.model_path = str(model_path)

            # Detect best device
            if torch.backends.mps.is_available():
                self.device = "mps"
                logger.info("🚀 Using Apple Metal Performance Shaders (MPS)")
            elif torch.cuda.is_available():
                self.device = "cuda"
                logger.info("🚀 Using CUDA GPU")
            else:
                self.device = "cpu"
                logger.info("🖥️ Using CPU")

            self.loaded = True
            logger.info(f"✅ YOLOv8 model loaded: {model_path}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to load YOLOv8 model: {e}")
            self.loaded = False
            return False

    async def detect_from_bytes(self, image_bytes: bytes) -> Dict:
        """
        Detect objects in image from bytes

        Args:
            image_bytes: Image data as bytes

        Returns:
            Detection results with objects, bounding boxes, confidence
        """
        if not self.loaded:
            if not YOLO_AVAILABLE:
                return self._mock_detection()
            await self.initialize()

        try:
            # Convert bytes to numpy array
            nparr = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if image is None:
                raise ValueError("Failed to decode image")

            return await self.detect(image)

        except Exception as e:
            logger.error(f"Error in detect_from_bytes: {e}")
            return {"error": str(e), "objects_detected": []}

    async def detect(self, image: np.ndarray) -> Dict:
        """
        Detect objects in OpenCV image

        Args:
            image: OpenCV image (numpy array)

        Returns:
            Detection results
        """
        if not self.loaded or not YOLO_AVAILABLE:
            return self._mock_detection()

        try:
            # Run inference
            results = self.model(image, device=self.device, verbose=False)

            # Parse results
            detections = []
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    class_id = int(box.cls[0])
                    confidence = float(box.conf[0])
                    bbox = box.xyxy[0].tolist()  # [x1, y1, x2, y2]

                    # Get class name
                    class_name = result.names[class_id]

                    # Check confidence threshold
                    threshold = self.confidence_thresholds.get(class_name, 0.5)
                    if confidence >= threshold:
                        detections.append({
                            "class": class_name,
                            "class_id": class_id,
                            "confidence": round(confidence, 3),
                            "bbox": [round(coord, 1) for coord in bbox]
                        })

            # Analyze threat level
            threat_analysis = self._analyze_threats(detections)

            return {
                "success": True,
                "objects_detected": detections,
                "object_count": len(detections),
                "threat_analysis": threat_analysis,
                "model_version": "yolov8n",
                "device": self.device
            }

        except Exception as e:
            logger.error(f"Error during detection: {e}")
            return {
                "success": False,
                "error": str(e),
                "objects_detected": []
            }

    def _analyze_threats(self, detections: List[Dict]) -> Dict:
        """Analyze detections for threats"""
        people_count = len([d for d in detections if d['class'] == 'person'])
        weapons_detected = any(d['class'] == 'weapon' for d in detections)
        vehicles = [d for d in detections if d['class'] in ['car', 'truck', 'motorcycle', 'bus']]

        threat_indicators = []
        if weapons_detected:
            threat_indicators.append("weapon_present")
        if people_count > 5:
            threat_indicators.append("large_crowd")
        if weapons_detected and people_count > 0:
            threat_indicators.append("armed_persons")

        # Calculate threat score (0-1)
        threat_score = 0.0
        if weapons_detected:
            threat_score += 0.8
        if people_count > 10:
            threat_score += 0.3
        elif people_count > 5:
            threat_score += 0.2
        threat_score = min(1.0, threat_score)

        return {
            "people_count": people_count,
            "weapons_detected": weapons_detected,
            "vehicle_count": len(vehicles),
            "threat_indicators": threat_indicators,
            "threat_score": round(threat_score, 2)
        }

    def _mock_detection(self) -> Dict:
        """Mock detection for when YOLO is unavailable"""
        return {
            "success": True,
            "objects_detected": [],
            "object_count": 0,
            "threat_analysis": {
                "people_count": 0,
                "weapons_detected": False,
                "vehicle_count": 0,
                "threat_indicators": [],
                "threat_score": 0.0
            },
            "model_version": "mock-detector",
            "device": "mock"
        }

    async def cleanup(self):
        """Cleanup resources"""
        self.model = None
        self.loaded = False
        logger.info("Visual detector cleaned up")


# Singleton instance
_visual_detector: Optional[VisualDetector] = None


async def get_visual_detector() -> VisualDetector:
    """Get or create visual detector singleton"""
    global _visual_detector
    if _visual_detector is None:
        _visual_detector = VisualDetector()
        await _visual_detector.initialize()
    return _visual_detector
