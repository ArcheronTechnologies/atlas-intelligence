"""
Threat Classification Service
Unified threat categorization across Halo, Frontline, SAIT_01
"""

import logging
import yaml
from pathlib import Path
from typing import Dict, Optional, List
import re

logger = logging.getLogger(__name__)


class ThreatClassifier:
    """AI-powered threat classification with unified taxonomy"""

    def __init__(self):
        self.taxonomy = None
        self.loaded = False
        logger.info("ThreatClassifier initialized")

    async def initialize(self):
        """Load threat taxonomy"""
        try:
            taxonomy_path = Path("config/threat_taxonomy.yaml")
            with open(taxonomy_path, 'r') as f:
                self.taxonomy = yaml.safe_load(f)
            self.loaded = True
            logger.info("✅ Threat taxonomy loaded successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to load threat taxonomy: {e}")
            return False

    async def classify_text(self, description: str, context: Optional[Dict] = None) -> Dict:
        """
        Classify threat from text description

        Args:
            description: Text description of incident
            context: Optional context (location, time, etc.)

        Returns:
            Classification result with unified categories
        """
        if not self.loaded:
            await self.initialize()

        # Simple keyword-based classification (MVP)
        # TODO: Replace with actual ML model in future

        description_lower = description.lower()

        # Keyword patterns for each category
        keywords = {
            'weapons': ['weapon', 'gun', 'knife', 'firearm', 'armed', 'pistol', 'rifle', 'shot', 'shooting', 'skott'],
            'violence': ['assault', 'attack', 'fight', 'beating', 'hit', 'punch', 'kick', 'violence', 'misshandel', 'våld'],
            'theft': ['theft', 'steal', 'rob', 'burglary', 'stolen', 'stöld', 'rån', 'inbrott'],
            'disturbance': ['noise', 'loud', 'disturbance', 'disorderly', 'complaint', 'ordningsstörning'],
            'vandalism': ['vandalism', 'damage', 'graffiti', 'destroy', 'skadegörelse', 'klotter'],
            'drug_activity': ['drug', 'narcotic', 'dealing', 'narkotika', 'knark'],
            'vehicle_crime': ['vehicle', 'car theft', 'hit and run', 'traffic', 'bil', 'fordon'],
            'suspicious_activity': ['suspicious', 'trespassing', 'loitering', 'misstänkt']
        }

        # Score each category
        scores = {}
        for category, category_keywords in keywords.items():
            score = sum(1 for kw in category_keywords if kw in description_lower)
            if score > 0:
                scores[category] = score

        # Determine best match
        if scores:
            threat_category = max(scores, key=scores.get)
            confidence = min(0.95, 0.6 + (scores[threat_category] * 0.1))
        else:
            threat_category = "suspicious_activity"
            confidence = 0.3

        # Get category details from taxonomy
        category_info = self.taxonomy.get(threat_category, {})
        severity_range = category_info.get('severity_range', [2, 3])
        severity = severity_range[1]  # Use max severity for keyword matches

        # Get product mappings
        halo_types = category_info.get('halo_types', [])
        frontline_objects = category_info.get('frontline_objects', [])
        sait_codes = category_info.get('sait_codes', [])
        polisen_types = category_info.get('polisen_types', [])

        return {
            "threat_category": threat_category,
            "threat_subcategory": halo_types[0] if halo_types else threat_category,
            "severity": severity,
            "confidence": confidence,
            "product_mappings": {
                "halo_incident_type": halo_types[0] if halo_types else threat_category,
                "polisen_type": polisen_types[0] if polisen_types else "Annan händelse",
                "frontline_objects": frontline_objects,
                "sait_threat_level": self._get_sait_level(severity)
            },
            "keywords_matched": list(scores.keys()),
            "model_version": "keyword-classifier-v0.1.0"
        }

    async def classify_visual(self, detected_objects: List[Dict]) -> Dict:
        """
        Classify threat from visual object detection

        Args:
            detected_objects: List of detected objects with confidence

        Returns:
            Classification result
        """
        if not self.loaded:
            await self.initialize()

        # Determine threat based on detected objects
        threat_category = "suspicious_activity"
        severity = 1
        confidence = 0.0

        has_weapon = any(obj['class'] in ['weapon', 'gun', 'knife'] for obj in detected_objects)
        has_person = any(obj['class'] == 'person' for obj in detected_objects)

        if has_weapon:
            threat_category = "weapons"
            severity = 5 if has_person else 4
            confidence = max((obj['confidence'] for obj in detected_objects if obj['class'] in ['weapon', 'gun', 'knife']), default=0.5)
        elif len([obj for obj in detected_objects if obj['class'] == 'person']) > 3:
            threat_category = "disturbance"
            severity = 2
            confidence = 0.7

        category_info = self.taxonomy.get(threat_category, {})
        halo_types = category_info.get('halo_types', [])
        polisen_types = category_info.get('polisen_types', [])

        return {
            "threat_category": threat_category,
            "threat_subcategory": halo_types[0] if halo_types else threat_category,
            "severity": severity,
            "confidence": confidence,
            "product_mappings": {
                "halo_incident_type": halo_types[0] if halo_types else threat_category,
                "polisen_type": polisen_types[0] if polisen_types else "Annan händelse",
                "frontline_objects": [obj['class'] for obj in detected_objects],
                "sait_threat_level": self._get_sait_level(severity)
            },
            "detected_objects": detected_objects,
            "model_version": "visual-classifier-v0.1.0"
        }

    async def classify_audio(self, audio_analysis: Dict) -> Dict:
        """
        Classify threat from audio analysis

        Args:
            audio_analysis: Audio analysis results (transcription, sounds detected)

        Returns:
            Classification result
        """
        if not self.loaded:
            await self.initialize()

        threat_category = "suspicious_activity"
        severity = 1
        confidence = 0.0

        threat_sounds = audio_analysis.get('threat_sounds', [])
        transcription = audio_analysis.get('transcription', '').lower()

        # Check for gunshots, explosions
        if any(sound['type'] in ['gunshot', 'explosion'] for sound in threat_sounds):
            threat_category = "weapons"
            severity = 5
            confidence = max((sound['confidence'] for sound in threat_sounds), default=0.8)
        # Check for distress signals
        elif any(sound['type'] in ['distress_scream', 'shouting'] for sound in threat_sounds):
            threat_category = "violence"
            severity = 4
            confidence = 0.7
        # Check transcription for keywords
        elif 'help' in transcription or 'police' in transcription:
            threat_category = "disturbance"
            severity = 3
            confidence = 0.6

        category_info = self.taxonomy.get(threat_category, {})
        halo_types = category_info.get('halo_types', [])
        sait_codes = category_info.get('sait_codes', [])
        polisen_types = category_info.get('polisen_types', [])

        return {
            "threat_category": threat_category,
            "threat_subcategory": halo_types[0] if halo_types else threat_category,
            "severity": severity,
            "confidence": confidence,
            "product_mappings": {
                "halo_incident_type": halo_types[0] if halo_types else threat_category,
                "polisen_type": polisen_types[0] if polisen_types else "Annan händelse",
                "frontline_objects": [],
                "sait_threat_level": self._get_sait_level(severity),
                "sait_codes": sait_codes
            },
            "threat_sounds": threat_sounds,
            "model_version": "audio-classifier-v0.1.0"
        }

    def _get_sait_level(self, severity: int) -> str:
        """Map severity number to SAIT threat level"""
        if severity >= 4:
            return "critical"
        elif severity == 3:
            return "moderate"
        else:
            return "low"


# Singleton instance
_threat_classifier: Optional[ThreatClassifier] = None


async def get_threat_classifier() -> ThreatClassifier:
    """Get or create threat classifier singleton"""
    global _threat_classifier
    if _threat_classifier is None:
        _threat_classifier = ThreatClassifier()
        await _threat_classifier.initialize()
    return _threat_classifier
