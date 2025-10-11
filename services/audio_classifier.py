"""
Audio Classifier Service for Atlas Intelligence
Adapted from SAIT_01 tactical audio detection system

ARCHITECTURE NOTE:
- SAIT_01 devices run TinyML models ON-DEVICE (nRF5340 edge inference)
- Atlas provides:
  1. Cloud verification for uncertain detections
  2. OTA model update hosting and distribution
  3. Cross-device intelligence aggregation
  4. Continuous model training from field data
  5. Higher-accuracy secondary analysis when requested

This is NOT a replacement for edge inference - it's a complement!
"""

import logging
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import asyncio

logger = logging.getLogger(__name__)

# Try to import audio processing libraries
try:
    import librosa
    import soundfile as sf
    AUDIO_LIBS_AVAILABLE = True
except ImportError:
    AUDIO_LIBS_AVAILABLE = False
    logger.warning("Audio libraries (librosa, soundfile) not available")


@dataclass
class AudioThreatCategory:
    """Audio threat category definition"""
    category: str
    priority: str  # 'IMMEDIATE_LETHAL', 'DIRECT_COMBAT', 'SURVEILLANCE', 'NON_THREAT'
    severity: int  # 1-5 scale
    sait_classes: List[int]  # SAIT class IDs
    keywords: List[str]


class AudioClassifierModel(nn.Module):
    """
    Multi-scale audio classification model
    Adapted from SAIT_01 production model for cloud deployment
    """

    def __init__(self, num_classes=30, input_dim=128):
        super().__init__()

        # Multi-scale feature extraction
        self.fc1 = nn.Linear(input_dim, 256)
        self.bn1 = nn.BatchNorm1d(256)

        self.fc2 = nn.Linear(256, 512)
        self.bn2 = nn.BatchNorm1d(512)

        self.fc3 = nn.Linear(512, 256)
        self.bn3 = nn.BatchNorm1d(256)

        # Classification head
        self.fc4 = nn.Linear(256, num_classes)

        self.dropout = nn.Dropout(0.3)

    def forward(self, x, return_features=False):
        """Forward pass through model"""
        x = F.relu(self.bn1(self.fc1(x)))
        x = self.dropout(x)

        x = F.relu(self.bn2(self.fc2(x)))
        x = self.dropout(x)

        features = F.relu(self.bn3(self.fc3(x)))
        logits = self.fc4(features)

        if return_features:
            return logits, features
        return logits


class AudioClassifier:
    """
    Cloud audio classification service for SAIT_01 integration

    Purpose:
    - Cloud verification for edge detections with confidence < threshold
    - Model training and OTA update distribution
    - Cross-device intelligence correlation
    - Higher accuracy when edge device requests cloud confirmation

    NOT a replacement for edge inference!
    """

    # SAIT_01 30-class threat taxonomy
    SAIT_CLASSES = {
        # Immediate lethal threats (weapons)
        0: 'small_arms_fire',
        1: 'artillery_fire',
        2: 'mortar_fire',
        3: 'rocket_launch',
        4: 'explosion_large',
        5: 'explosion_small',

        # Direct combat vehicles
        6: 'tank_movement',
        7: 'apc_movement',
        8: 'truck_convoy',
        9: 'helicopter_rotor',
        10: 'jet_aircraft',
        11: 'propeller_aircraft',

        # Human activity / surveillance
        12: 'radio_chatter',
        13: 'shouting_commands',
        14: 'footsteps_marching',
        15: 'equipment_clanking',

        # Mechanical sounds
        16: 'engine_idle',
        17: 'engine_revving',
        18: 'door_slam',
        19: 'metal_impact',
        20: 'glass_breaking',
        21: 'alarm_siren',
        22: 'whistle_signal',
        23: 'crowd_noise',

        # Environmental
        24: 'construction_noise',
        25: 'ambient_quiet',
        26: 'wind_noise',

        # Aerial threats
        27: 'drone_acoustic',
        28: 'helicopter_military',
        29: 'aerial_background',
    }

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self.model: Optional[AudioClassifierModel] = None
        self.device = self._get_device()
        self.loaded = False

        # Audio processing parameters
        self.sample_rate = 16000
        self.n_mels = 128
        self.hop_length = 512
        self.n_fft = 2048

        # Threat category mappings (SAIT → Atlas taxonomy)
        self.threat_categories = self._define_threat_categories()

        logger.info("AudioClassifier initialized")
        logger.warning("⚠️ BETA: Audio classifier model needs retraining with production data")

    def _get_device(self) -> str:
        """Determine best available device"""
        if torch.cuda.is_available():
            return "cuda"
        elif torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _define_threat_categories(self) -> Dict[str, AudioThreatCategory]:
        """Map SAIT classes to Atlas threat categories"""
        return {
            'weapons': AudioThreatCategory(
                category='weapons',
                priority='IMMEDIATE_LETHAL',
                severity=5,
                sait_classes=[0, 1, 2, 3, 4, 5],  # All weapon sounds
                keywords=['gunshot', 'explosion', 'artillery', 'mortar', 'rocket']
            ),
            'violence': AudioThreatCategory(
                category='violence',
                priority='DIRECT_COMBAT',
                severity=4,
                sait_classes=[13, 14, 15, 20, 23],  # Shouting, marching, glass break, crowd
                keywords=['shouting', 'commands', 'fighting', 'breaking', 'crowd']
            ),
            'vehicle_military': AudioThreatCategory(
                category='vehicle_crime',  # Maps to Atlas taxonomy
                priority='DIRECT_COMBAT',
                severity=4,
                sait_classes=[6, 7, 8, 27, 28],  # Military vehicles, drones
                keywords=['tank', 'apc', 'convoy', 'helicopter', 'drone']
            ),
            'vehicle_civilian': AudioThreatCategory(
                category='vehicle_crime',
                priority='SURVEILLANCE',
                severity=2,
                sait_classes=[9, 10, 11, 16, 17],  # Civilian aircraft, engines
                keywords=['aircraft', 'engine', 'vehicle']
            ),
            'disturbance': AudioThreatCategory(
                category='disturbance',
                priority='SURVEILLANCE',
                severity=2,
                sait_classes=[12, 21, 22, 23, 24],  # Radio, alarm, construction
                keywords=['alarm', 'siren', 'construction', 'noise']
            ),
            'suspicious_activity': AudioThreatCategory(
                category='suspicious_activity',
                priority='SURVEILLANCE',
                severity=2,
                sait_classes=[15, 18, 19],  # Equipment, doors, metal
                keywords=['equipment', 'metal', 'suspicious']
            ),
            'background': AudioThreatCategory(
                category='background',
                priority='NON_THREAT',
                severity=1,
                sait_classes=[25, 26, 29],  # Quiet, wind, aerial background
                keywords=['ambient', 'wind', 'quiet']
            ),
        }

    async def load_model(self):
        """Load the audio classification model"""
        try:
            # Initialize model
            self.model = AudioClassifierModel(num_classes=30, input_dim=128)

            # Try to load pretrained weights if available
            if self.model_path and Path(self.model_path).exists():
                logger.info(f"Loading audio model from {self.model_path}")
                state_dict = torch.load(self.model_path, map_location=self.device)
                self.model.load_state_dict(state_dict)
                logger.info("✅ Pretrained audio model loaded")
            else:
                logger.warning("⚠️ No pretrained model found, using untrained model")
                logger.warning("   For production, train model from SAIT_01 codebase")

            self.model = self.model.to(self.device)
            self.model.eval()
            self.loaded = True

            logger.info(f"✅ Audio classifier ready on {self.device}")

        except Exception as e:
            logger.error(f"Failed to load audio model: {e}")
            self.loaded = False

    def extract_features(self, audio_data: np.ndarray, sr: int = None) -> np.ndarray:
        """
        Extract mel-spectrogram features from audio

        Args:
            audio_data: Raw audio samples
            sr: Sample rate (will resample if different from 16kHz)

        Returns:
            Feature vector (128-dim mel-spectrogram features)
        """
        if not AUDIO_LIBS_AVAILABLE:
            # Fallback: use mock features
            logger.warning("Audio libs not available, using mock features")
            return np.random.randn(128).astype(np.float32)

        try:
            # Resample if needed
            if sr and sr != self.sample_rate:
                audio_data = librosa.resample(
                    audio_data,
                    orig_sr=sr,
                    target_sr=self.sample_rate
                )

            # Compute mel-spectrogram
            mel_spec = librosa.feature.melspectrogram(
                y=audio_data,
                sr=self.sample_rate,
                n_mels=self.n_mels,
                hop_length=self.hop_length,
                n_fft=self.n_fft
            )

            # Convert to log scale
            log_mel_spec = librosa.power_to_db(mel_spec, ref=np.max)

            # Aggregate across time (mean pooling)
            features = np.mean(log_mel_spec, axis=1)

            # Normalize
            features = (features - features.mean()) / (features.std() + 1e-8)

            return features.astype(np.float32)

        except Exception as e:
            logger.error(f"Feature extraction failed: {e}")
            # Return mock features as fallback
            return np.random.randn(128).astype(np.float32)

    async def classify_audio(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        context: Optional[Dict] = None
    ) -> Dict:
        """
        Classify audio threat

        Args:
            audio_data: Raw audio samples (numpy array)
            sample_rate: Sample rate of audio
            context: Additional context (location, time, etc.)

        Returns:
            Classification result with threat category and confidence
        """
        if not self.loaded:
            await self.load_model()

        try:
            # Extract features
            features = self.extract_features(audio_data, sample_rate)

            # Run inference
            with torch.no_grad():
                features_tensor = torch.FloatTensor(features).unsqueeze(0).to(self.device)
                logits = self.model(features_tensor)
                probs = F.softmax(logits, dim=1)

                # Get top predictions
                top_prob, top_class = torch.max(probs, dim=1)
                top_prob = top_prob.item()
                top_class = top_class.item()

            # Map SAIT class to Atlas threat category
            sait_threat = self.SAIT_CLASSES.get(top_class, 'unknown')
            atlas_category = self._map_sait_to_atlas(top_class)

            # Get category info
            category_info = self.threat_categories.get(atlas_category, {})

            result = {
                'success': True,
                'beta': True,  # Mark audio classifier as beta
                'threat_category': atlas_category,
                'severity': category_info.severity if category_info else 1,
                'confidence': float(top_prob),
                'sait_classification': {
                    'class_id': int(top_class),
                    'class_name': sait_threat,
                    'priority': category_info.priority if category_info else 'UNKNOWN'
                },
                'audio_metadata': {
                    'sample_rate': sample_rate,
                    'duration_seconds': len(audio_data) / sample_rate,
                    'feature_dim': features.shape[0]
                },
                'recommendations': self._generate_recommendations(atlas_category, top_prob)
            }

            logger.info(f"Audio classified: {atlas_category} (confidence: {top_prob:.2f})")
            return result

        except Exception as e:
            logger.error(f"Audio classification failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'threat_category': 'unknown',
                'confidence': 0.0
            }

    def _map_sait_to_atlas(self, sait_class: int) -> str:
        """Map SAIT class ID to Atlas threat category"""
        for category_name, category_info in self.threat_categories.items():
            if sait_class in category_info.sait_classes:
                return category_name
        return 'suspicious_activity'  # Default fallback

    def _generate_recommendations(self, category: str, confidence: float) -> List[str]:
        """Generate recommendations based on classification"""
        recommendations = []

        if category == 'weapons' and confidence > 0.7:
            recommendations.append("IMMEDIATE: Gunshot/explosion detected - alert authorities")
            recommendations.append("Evacuate area if safe to do so")
            recommendations.append("Record location and time for investigation")
        elif category == 'violence' and confidence > 0.6:
            recommendations.append("Physical altercation detected - notify security")
            recommendations.append("Monitor situation for escalation")
        elif category == 'vehicle_military' and confidence > 0.8:
            recommendations.append("Military vehicle/drone detected")
            recommendations.append("Verify source and context")
        elif category == 'disturbance':
            recommendations.append("Public disturbance - standard monitoring")

        return recommendations


    async def verify_edge_detection(
        self,
        sait_detection: Dict,
        audio_data: Optional[np.ndarray] = None
    ) -> Dict:
        """
        Verify edge detection from SAIT device with cloud model

        Args:
            sait_detection: Detection from edge device with confidence
            audio_data: Optional raw audio for re-analysis

        Returns:
            Verification result with cloud confidence
        """
        edge_class = sait_detection.get('class_id')
        edge_confidence = sait_detection.get('confidence', 0.0)

        # If edge confidence is high, trust it
        if edge_confidence > 0.85:
            return {
                'verified': True,
                'edge_confidence': edge_confidence,
                'cloud_confidence': edge_confidence,  # Trust edge
                'action': 'edge_detection_trusted',
                'message': 'High edge confidence - no cloud verification needed'
            }

        # Low confidence - re-analyze with cloud model
        if audio_data is not None and self.loaded:
            cloud_result = await self.classify_audio(audio_data)

            agreement = (
                cloud_result['sait_classification']['class_id'] == edge_class
            )

            return {
                'verified': agreement,
                'edge_confidence': edge_confidence,
                'cloud_confidence': cloud_result['confidence'],
                'edge_class': edge_class,
                'cloud_class': cloud_result['sait_classification']['class_id'],
                'action': 'cloud_verified' if agreement else 'cloud_disagrees',
                'final_category': cloud_result['threat_category'],
                'recommendations': cloud_result['recommendations']
            }

        # No audio provided - can only flag for review
        return {
            'verified': False,
            'edge_confidence': edge_confidence,
            'action': 'flagged_for_review',
            'message': 'Low edge confidence, no audio for cloud verification'
        }

    def get_model_version(self) -> Dict:
        """Get current model version for OTA updates"""
        return {
            'model_version': '1.0.0',
            'model_type': 'audio_classifier',
            'architecture': 'MultiScaleAudioModel',
            'num_classes': 30,
            'input_dim': 128,
            'format': 'pytorch',
            'deployed_at': '2025-10-07',
            'compatible_devices': ['nRF5340', 'SAIT_01']
        }

    async def get_ota_model_package(self, target_format: str = 'tflite') -> Optional[bytes]:
        """
        Get model package for OTA update to SAIT devices

        Args:
            target_format: 'tflite', 'cmsis-nn', or 'pytorch'

        Returns:
            Model bytes for OTA distribution
        """
        if not self.loaded or not self.model_path:
            logger.warning("No model available for OTA distribution")
            return None

        try:
            model_file = Path(self.model_path)
            if not model_file.exists():
                return None

            # For now, return raw PyTorch model
            # TODO: Convert to TFLite/CMSIS-NN for edge deployment
            with open(model_file, 'rb') as f:
                model_bytes = f.read()

            logger.info(f"OTA package prepared: {len(model_bytes)} bytes")
            return model_bytes

        except Exception as e:
            logger.error(f"OTA package preparation failed: {e}")
            return None


# Singleton instance
_audio_classifier: Optional[AudioClassifier] = None


async def get_audio_classifier(model_path: Optional[str] = None) -> AudioClassifier:
    """Get or create audio classifier singleton"""
    global _audio_classifier

    if _audio_classifier is None:
        if model_path is None:
            # Try to find SAIT model
            sait_models = [
                Path("models/sait_audio_classifier.pth"),
                Path("models/production_model_best.pth"),
                Path("/Users/timothyaikenhead/Desktop/SAIT_01 Firmware:Software/production_model_best.pth"),
            ]
            for model in sait_models:
                if model.exists():
                    model_path = str(model)
                    break

        _audio_classifier = AudioClassifier(model_path=model_path)
        await _audio_classifier.load_model()

    return _audio_classifier
