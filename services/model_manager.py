"""
Unified Model Manager - Singleton pattern for shared ML models
All products (Halo, SAIT, Frontline) share the same model instances
"""

import logging
from typing import Optional
import asyncio

from services.threat_classifier import ThreatClassifier
from services.visual_detector import VisualDetector
from services.audio_classifier import AudioClassifier

logger = logging.getLogger(__name__)


class ModelManager:
    """
    Singleton model manager - ensures models are loaded once and shared

    Benefits:
    - Memory efficient: 1x model loading instead of 3x
    - Consistency: Same input → same output across all products
    - Better training: All products contribute to single model improvement
    - Simpler ops: One model version to manage
    """

    _instance: Optional['ModelManager'] = None
    _lock = asyncio.Lock()
    _initialized = False

    def __init__(self):
        """Private constructor - use get_instance() instead"""
        self._threat_classifier: Optional[ThreatClassifier] = None
        self._visual_detector: Optional[VisualDetector] = None
        self._audio_classifier: Optional[AudioClassifier] = None

    @classmethod
    async def get_instance(cls) -> 'ModelManager':
        """Get singleton instance (thread-safe)"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    await cls._instance._initialize()
        return cls._instance

    async def _initialize(self):
        """Initialize all models (called once on first access)"""
        if self._initialized:
            return

        logger.info("🚀 Initializing Model Manager (singleton)")

        try:
            # Load threat classifier
            logger.info("Loading threat classifier...")
            from services.threat_classifier import get_threat_classifier
            self._threat_classifier = await get_threat_classifier()
            logger.info("✅ Threat classifier loaded")

            # Load visual detector
            logger.info("Loading visual detector...")
            from services.visual_detector import get_visual_detector
            self._visual_detector = await get_visual_detector()
            logger.info("✅ Visual detector loaded")

            # Load audio classifier
            logger.info("Loading audio classifier...")
            from services.audio_classifier import get_audio_classifier
            self._audio_classifier = await get_audio_classifier()
            logger.info("✅ Audio classifier loaded")

            self._initialized = True
            logger.info("🎉 Model Manager initialized - all models ready and shared")

        except Exception as e:
            logger.error(f"❌ Model Manager initialization failed: {e}")
            raise

    @property
    def threat_classifier(self) -> ThreatClassifier:
        """Get shared threat classifier instance"""
        if not self._initialized:
            raise RuntimeError("Model Manager not initialized - call get_instance() first")
        return self._threat_classifier

    @property
    def visual_detector(self) -> VisualDetector:
        """Get shared visual detector instance"""
        if not self._initialized:
            raise RuntimeError("Model Manager not initialized - call get_instance() first")
        return self._visual_detector

    @property
    def audio_classifier(self) -> AudioClassifier:
        """Get shared audio classifier instance"""
        if not self._initialized:
            raise RuntimeError("Model Manager not initialized - call get_instance() first")
        return self._audio_classifier

    def get_model_info(self) -> dict:
        """Get information about loaded models"""
        return {
            "initialized": self._initialized,
            "models": {
                "threat_classifier": {
                    "loaded": self._threat_classifier is not None,
                    "type": "ThreatClassifier",
                    "shared_by": ["Halo", "SAIT", "Frontline"]
                },
                "visual_detector": {
                    "loaded": self._visual_detector is not None,
                    "type": "VisualDetector (YOLOv8)",
                    "shared_by": ["Halo", "Frontline"]
                },
                "audio_classifier": {
                    "loaded": self._audio_classifier is not None,
                    "type": "AudioClassifier (30 SAIT classes)",
                    "shared_by": ["Halo", "SAIT", "Frontline"]
                }
            },
            "architecture": "central_stack",
            "memory_efficiency": "3x better than separate instances"
        }


# Global singleton access
_model_manager: Optional[ModelManager] = None


async def get_model_manager() -> ModelManager:
    """
    Get the global model manager singleton

    Usage:
        manager = await get_model_manager()
        classifier = manager.threat_classifier
        result = await classifier.classify_threat(...)
    """
    global _model_manager

    if _model_manager is None:
        _model_manager = await ModelManager.get_instance()

    return _model_manager
