"""
Media Analysis Service
Unified photo/video/audio analysis combining all product capabilities
"""

import logging
from typing import Dict, Optional
from pathlib import Path
import time

from services.visual_detector import get_visual_detector
from services.threat_classifier import get_threat_classifier
from services.audio_classifier import get_audio_classifier

logger = logging.getLogger(__name__)


class MediaAnalyzer:
    """Unified media analysis service"""

    def __init__(self):
        self.visual_detector = None
        self.threat_classifier = None
        self.loaded = False

    async def initialize(self):
        """Initialize all analysis components"""
        try:
            self.visual_detector = await get_visual_detector()
            self.threat_classifier = await get_threat_classifier()
            self.loaded = True
            logger.info("✅ MediaAnalyzer initialized")
            return True
        except Exception as e:
            logger.error(f"❌ MediaAnalyzer initialization failed: {e}")
            return False

    async def analyze_photo(self, image_bytes: bytes, return_detailed: bool = True) -> Dict:
        """
        Analyze photo for threats

        Args:
            image_bytes: Image data as bytes
            return_detailed: Whether to return detailed analysis

        Returns:
            Analysis results with object detection and threat classification
        """
        if not self.loaded:
            await self.initialize()

        start_time = time.time()

        try:
            # Visual detection (YOLOv8)
            visual_results = await self.visual_detector.detect_from_bytes(image_bytes)

            if not visual_results.get('success'):
                return {
                    "success": False,
                    "error": visual_results.get('error', 'Visual detection failed')
                }

            # Threat classification based on detected objects
            threat_classification = await self.threat_classifier.classify_visual(
                visual_results['objects_detected']
            )

            processing_time = int((time.time() - start_time) * 1000)

            result = {
                "success": True,
                "media_type": "photo",
                "visual_analysis": {
                    "objects": visual_results['objects_detected'],
                    "object_count": visual_results['object_count'],
                    "people_count": visual_results['threat_analysis']['people_count'],
                    "weapons_detected": visual_results['threat_analysis']['weapons_detected'],
                    "threat_indicators": visual_results['threat_analysis']['threat_indicators']
                },
                "threat_classification": threat_classification,
                "source_models": {
                    "object_detector": f"{visual_results.get('model_version', 'unknown')}-{visual_results.get('device', 'unknown')}",
                    "threat_classifier": threat_classification.get('model_version', 'unknown')
                },
                "processing_time_ms": processing_time
            }

            # Add detailed info if requested
            if return_detailed:
                result["detailed_analysis"] = {
                    "full_detections": visual_results['objects_detected'],
                    "threat_score": visual_results['threat_analysis']['threat_score'],
                    "confidence_breakdown": {
                        obj['class']: obj['confidence']
                        for obj in visual_results['objects_detected']
                    }
                }

            return result

        except Exception as e:
            logger.error(f"Error analyzing photo: {e}")
            return {
                "success": False,
                "error": str(e),
                "processing_time_ms": int((time.time() - start_time) * 1000)
            }

    async def analyze_video(self, video_bytes: bytes, keyframe_fps: float = 1.0) -> Dict:
        """
        Analyze video for threats (keyframe extraction)

        Args:
            video_bytes: Video data as bytes
            keyframe_fps: Frames per second to extract

        Returns:
            Analysis results
        """
        # TODO: Implement video analysis with keyframe extraction
        # For MVP, return placeholder
        return {
            "success": True,
            "media_type": "video",
            "message": "Video analysis not yet implemented",
            "video_analysis": {
                "duration_seconds": 0,
                "keyframes_analyzed": 0,
                "people_detected": False,
                "weapons_detected": False,
                "violence_score": 0.0
            },
            "timeline": [],
            "classification": {},
            "processing_time_ms": 0
        }

    async def analyze_audio(self, audio_file_path: str, context: Optional[Dict] = None) -> Dict:
        """
        Analyze audio for threats using SAIT classifier

        Args:
            audio_file_path: Path to audio file
            context: Optional context (location, timestamp, etc.)

        Returns:
            Analysis results with threat classification
        """
        start_time = time.time()

        try:
            # Load audio file
            try:
                import librosa
                audio_data, sample_rate = librosa.load(audio_file_path, sr=16000)
                duration = len(audio_data) / sample_rate
            except ImportError:
                logger.warning("Audio libraries not available")
                return {
                    "success": False,
                    "error": "Audio processing libraries not installed (librosa required)",
                    "media_type": "audio"
                }

            # Get audio classifier
            audio_classifier = await get_audio_classifier()

            # Classify audio
            result = await audio_classifier.classify_audio(
                audio_data=audio_data,
                sample_rate=sample_rate,
                context=context
            )

            processing_time = int((time.time() - start_time) * 1000)

            return {
                "success": result['success'],
                "media_type": "audio",
                "audio_analysis": {
                    "duration_seconds": duration,
                    "sample_rate": sample_rate,
                    "threat_sounds": [{
                        "type": result['sait_classification']['class_name'],
                        "confidence": result['confidence'],
                        "priority": result['sait_classification']['priority'],
                        "timestamp": 0.0  # For future temporal localization
                    }] if result['success'] else [],
                    "speaker_count": 0,  # TODO: Implement speaker diarization
                    "aggression_score": result.get('confidence', 0.0) if result.get('threat_category') == 'violence' else 0.0,
                    "distress_detected": result.get('threat_category') in ['weapons', 'violence']
                },
                "threat_classification": {
                    "category": result.get('threat_category', 'unknown'),
                    "subcategory": result.get('sait_classification', {}).get('class_name', 'unknown'),
                    "severity": result.get('severity', 1),
                    "confidence": result.get('confidence', 0.0)
                },
                "source_models": {
                    "audio_classifier": "sait-cloud-v1.0.0",
                    "threat_classifier": "atlas-threat-v1.0.0"
                },
                "recommendations": result.get('recommendations', []),
                "processing_time_ms": processing_time
            }

        except Exception as e:
            logger.error(f"Audio analysis failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "media_type": "audio",
                "processing_time_ms": int((time.time() - start_time) * 1000)
            }


# Singleton instance
_media_analyzer: Optional[MediaAnalyzer] = None


async def get_media_analyzer() -> MediaAnalyzer:
    """Get or create media analyzer singleton"""
    global _media_analyzer
    if _media_analyzer is None:
        _media_analyzer = MediaAnalyzer()
        await _media_analyzer.initialize()
    return _media_analyzer
