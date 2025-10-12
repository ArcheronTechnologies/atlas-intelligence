# Halo ↔ Atlas Intelligence Integration Plan

**Date:** October 7, 2025
**Status:** Planning Phase
**Timeline:** Week 3 of 6-week roadmap

---

## 📋 Overview

This document outlines the integration plan for connecting **Halo** (public safety app) with **Atlas Intelligence** (shared AI/ML backbone).

### Goals
1. Replace Halo's local ML processing with Atlas API calls
2. Maintain graceful degradation if Atlas is unavailable
3. Enrich Halo incidents with cross-product intelligence
4. Reduce Halo infrastructure costs by ~$30/month
5. Improve classification accuracy through combined training data

---

## 🏗️ Architecture

### Current State (Halo Standalone)
```
Halo Mobile App
    ↓
Halo Backend (FastAPI)
    ├── Local incident classifier
    ├── Local photo analyzer
    ├── Local audio analyzer
    └── PostgreSQL (operational data)
```

### Target State (Halo + Atlas)
```
Halo Mobile App
    ↓
Halo Backend (FastAPI)
    ├── Atlas Client Library ← NEW
    │   ├── classify_incident()
    │   ├── analyze_media()
    │   ├── send_feedback()
    │   └── get_patterns()
    ↓
Atlas Intelligence API
    ├── Threat Classification
    ├── Media Analysis
    ├── Intelligence Patterns
    └── Training Pipeline

Halo PostgreSQL (operational data + Atlas metadata)
```

---

## 🔌 Integration Points

### 1. **Incident Creation** (Primary Integration)

**Current Flow:**
```python
# Halo: backend/api/incidents.py
@router.post("/api/v1/incidents")
async def create_incident(incident: IncidentCreate):
    # Local classification
    category = local_classifier.classify(incident.description)

    # Save to Halo DB
    await db.save_incident(incident, category)

    return incident_id
```

**New Flow with Atlas:**
```python
# Halo: backend/api/incidents.py
from services.atlas_client import atlas_client

@router.post("/api/v1/incidents")
async def create_incident(incident: IncidentCreate):
    # Call Atlas for classification
    try:
        atlas_result = await atlas_client.classify_incident(
            description=incident.description,
            location=(incident.latitude, incident.longitude),
            occurred_at=incident.occurred_at
        )

        category = atlas_result['classification']['threat_category']
        severity = atlas_result['classification']['severity']
        confidence = atlas_result['classification']['confidence']
        atlas_threat_id = atlas_result['threat_id']

    except AtlasUnavailableError:
        # Fallback to basic local classification
        category = basic_local_classifier(incident.description)
        severity = 2  # default
        confidence = 0.5
        atlas_threat_id = None

    # Save to Halo DB with Atlas metadata
    await db.save_incident(
        incident,
        category=category,
        severity=severity,
        atlas_threat_id=atlas_threat_id,
        atlas_classification=atlas_result
    )

    return incident_id
```

---

### 2. **Media Analysis** (Photo/Video/Audio)

**Current Flow:**
```python
# Halo: backend/api/media_api.py
@router.post("/analyze/photo")
async def analyze_photo(file: UploadFile):
    # Local YOLOv8 detection
    objects = await local_yolo.detect(file)
    threats = classify_objects(objects)

    return {"threats": threats, "objects": objects}
```

**New Flow with Atlas:**
```python
# Halo: backend/api/media_api.py
@router.post("/analyze/photo")
async def analyze_photo(file: UploadFile):
    try:
        # Send to Atlas for analysis
        result = await atlas_client.analyze_media(
            media_file=file,
            media_type="photo",
            context={"incident_id": incident_id}
        )

        return result

    except AtlasUnavailableError:
        # Fallback: return basic info
        return {"error": "Atlas unavailable", "objects": []}
```

---

### 3. **Intelligence Patterns** (New Feature)

**New Capability with Atlas:**
```python
# Halo: backend/api/intelligence.py (NEW)
@router.get("/intelligence/patterns")
async def get_nearby_patterns(
    lat: float,
    lon: float,
    radius_km: float = 5.0
):
    # Get patterns from Atlas
    patterns = await atlas_client.get_patterns(
        location=(lat, lon),
        radius_km=radius_km,
        time_range="7d"
    )

    # Enrich Halo incidents with pattern data
    return {
        "patterns": patterns,
        "recommendations": generate_recommendations(patterns)
    }
```

---

### 4. **Training Feedback** (Continuous Improvement)

**New Flow:**
```python
# Halo: backend/api/incidents.py
@router.patch("/api/v1/incidents/{incident_id}/validate")
async def validate_incident(
    incident_id: UUID,
    actual_category: str,
    validated_by: str
):
    incident = await db.get_incident(incident_id)

    # Send feedback to Atlas
    if incident.atlas_threat_id:
        await atlas_client.send_feedback(
            threat_id=incident.atlas_threat_id,
            predicted_category=incident.category,
            actual_category=actual_category,
            validated_by=validated_by
        )

    # Update Halo DB
    await db.update_incident(incident_id, category=actual_category)
```

---

## 📊 Database Schema Changes

### Halo Database Updates

**New columns for `crime_incidents` table:**
```sql
ALTER TABLE crime_incidents ADD COLUMN atlas_threat_id UUID;
ALTER TABLE crime_incidents ADD COLUMN atlas_classification JSONB;
ALTER TABLE crime_incidents ADD COLUMN atlas_last_sync TIMESTAMP;
ALTER TABLE crime_incidents ADD COLUMN atlas_confidence FLOAT;
ALTER TABLE crime_incidents ADD COLUMN atlas_severity INTEGER;

CREATE INDEX idx_atlas_threat_id ON crime_incidents(atlas_threat_id);
CREATE INDEX idx_atlas_sync ON crime_incidents(atlas_last_sync);
```

**Example data:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "incident_type": "assault",
  "description": "Fight outside bar",
  "latitude": 59.3293,
  "longitude": 18.0686,

  // NEW: Atlas integration fields
  "atlas_threat_id": "7f3d9c21-8a5b-4e67-9c11-2b8e5f7d3a12",
  "atlas_classification": {
    "threat_category": "violence",
    "threat_subcategory": "physical_altercation",
    "severity": 4,
    "confidence": 0.87,
    "product_mappings": {
      "halo_incident_type": "assault",
      "polisen_type": "Misshandel"
    }
  },
  "atlas_confidence": 0.87,
  "atlas_severity": 4,
  "atlas_last_sync": "2025-10-07T19:15:00Z"
}
```

---

## 🔧 Atlas Client Library

**Location:** `/Users/timothyaikenhead/Desktop/Halo/backend/services/atlas_client.py` (NEW FILE)

```python
"""
Atlas Intelligence Client for Halo
Handles all communication with Atlas API
"""

import os
import aiohttp
from typing import Dict, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AtlasUnavailableError(Exception):
    """Raised when Atlas API is unavailable"""
    pass


class AtlasClient:
    """Client for Atlas Intelligence API"""

    def __init__(
        self,
        api_url: str = None,
        api_key: str = None,
        timeout: int = 10,
        retry_count: int = 2
    ):
        self.api_url = api_url or os.getenv("ATLAS_API_URL", "https://atlas.railway.app")
        self.api_key = api_key or os.getenv("ATLAS_API_KEY")
        self.timeout = timeout
        self.retry_count = retry_count
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={
                "X-API-Key": self.api_key,
                "X-Product": "halo",
                "Content-Type": "application/json"
            },
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def classify_incident(
        self,
        description: str,
        location: Tuple[float, float],
        occurred_at: datetime = None,
        incident_type: str = None
    ) -> Dict:
        """
        Classify incident threat level

        Args:
            description: Incident description text
            location: (latitude, longitude) tuple
            occurred_at: When incident occurred
            incident_type: Optional Halo incident type

        Returns:
            Classification result from Atlas

        Raises:
            AtlasUnavailableError: If Atlas API is down
        """
        payload = {
            "type": "text",
            "data": description,
            "context": {
                "latitude": location[0],
                "longitude": location[1],
                "timestamp": (occurred_at or datetime.now()).isoformat(),
                "source_product": "halo",
                "incident_type": incident_type
            },
            "options": {
                "include_nearby_patterns": True,
                "correlation_threshold": 0.7
            }
        }

        try:
            async with self.session.post(
                f"{self.api_url}/api/v1/classify/threat",
                json=payload
            ) as response:
                response.raise_for_status()
                return await response.json()

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Atlas API error: {e}")
            raise AtlasUnavailableError(f"Atlas unavailable: {e}")

    async def analyze_media(
        self,
        media_file,
        media_type: str,
        context: Dict = None
    ) -> Dict:
        """
        Analyze photo/video/audio media

        Args:
            media_file: File upload
            media_type: "photo", "video", or "audio"
            context: Additional context (incident_id, etc.)

        Returns:
            Media analysis result
        """
        data = aiohttp.FormData()
        data.add_field('file', media_file)
        data.add_field('media_type', media_type)
        if context:
            data.add_field('context', json.dumps(context))

        try:
            async with self.session.post(
                f"{self.api_url}/api/v1/analyze/media",
                data=data
            ) as response:
                response.raise_for_status()
                return await response.json()

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Atlas media analysis error: {e}")
            raise AtlasUnavailableError(f"Atlas unavailable: {e}")

    async def send_feedback(
        self,
        threat_id: str,
        predicted_category: str,
        actual_category: str,
        validated_by: str = None
    ) -> Dict:
        """
        Send validation feedback to Atlas

        Args:
            threat_id: Atlas threat intelligence ID
            predicted_category: What Atlas predicted
            actual_category: Actual validated category
            validated_by: Who validated (user_id or "law_enforcement")

        Returns:
            Feedback acknowledgment
        """
        payload = {
            "source_product": "halo",
            "prediction_id": threat_id,
            "predicted_category": predicted_category,
            "actual_category": actual_category,
            "user_correction": True,
            "correction_metadata": {
                "corrected_by": validated_by,
                "correction_timestamp": datetime.now().isoformat()
            }
        }

        try:
            async with self.session.post(
                f"{self.api_url}/api/v1/training/feedback",
                json=payload
            ) as response:
                response.raise_for_status()
                return await response.json()

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.warning(f"Atlas feedback failed (non-critical): {e}")
            return {"success": False, "error": str(e)}

    async def get_patterns(
        self,
        location: Tuple[float, float],
        radius_km: float = 5.0,
        time_range: str = "7d",
        threat_types: list = None
    ) -> Dict:
        """
        Get intelligence patterns near location

        Args:
            location: (latitude, longitude) tuple
            radius_km: Search radius in kilometers
            time_range: Time window (e.g., "7d", "30d")
            threat_types: Optional list of threat categories to filter

        Returns:
            Intelligence patterns from Atlas
        """
        params = {
            "lat": location[0],
            "lon": location[1],
            "radius_km": radius_km,
            "time_range": time_range,
            "min_significance": 0.7
        }

        if threat_types:
            params["threat_types"] = ",".join(threat_types)

        try:
            async with self.session.get(
                f"{self.api_url}/api/v1/intelligence/patterns",
                params=params
            ) as response:
                response.raise_for_status()
                return await response.json()

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.warning(f"Atlas patterns unavailable: {e}")
            return {"patterns": [], "count": 0}


# Singleton instance
_atlas_client: Optional[AtlasClient] = None


async def get_atlas_client() -> AtlasClient:
    """Get or create Atlas client singleton"""
    global _atlas_client
    if _atlas_client is None:
        _atlas_client = AtlasClient()
        await _atlas_client.__aenter__()
    return _atlas_client
```

---

## ⚙️ Configuration

### Environment Variables

**Halo Backend `.env` additions:**
```bash
# Atlas Integration
ATLAS_API_URL=https://atlas-intelligence.railway.app
ATLAS_API_KEY=halo_api_key_xxxxxxxxxxxxxxxx
ATLAS_TIMEOUT=10
ATLAS_RETRY_COUNT=2
ATLAS_FALLBACK_ENABLED=true
```

**Atlas Backend `.env` additions:**
```bash
# Product API Keys
API_KEY_HALO=halo_api_key_xxxxxxxxxxxx
API_KEY_FRONTLINE=frontline_api_key_xxxxxxxxx
API_KEY_SAIT=sait_api_key_xxxxxxxxx
```

---

## 🧪 Testing Plan

### 1. Unit Tests
```python
# tests/test_atlas_client.py
import pytest
from services.atlas_client import AtlasClient, AtlasUnavailableError

@pytest.mark.asyncio
async def test_classify_incident():
    async with AtlasClient(api_url="http://localhost:8001") as client:
        result = await client.classify_incident(
            description="Fight outside bar",
            location=(59.3293, 18.0686)
        )

        assert result['classification']['threat_category'] in ['violence', 'disturbance']
        assert 1 <= result['classification']['severity'] <= 5

@pytest.mark.asyncio
async def test_atlas_unavailable_fallback():
    async with AtlasClient(api_url="http://localhost:9999") as client:
        with pytest.raises(AtlasUnavailableError):
            await client.classify_incident(
                description="Test",
                location=(59.0, 18.0)
            )
```

### 2. Integration Tests
```python
# tests/test_halo_atlas_integration.py
@pytest.mark.asyncio
async def test_incident_creation_with_atlas():
    # Create incident via Halo API
    response = await test_client.post("/api/v1/incidents", json={
        "description": "Gunshots heard",
        "latitude": 59.3293,
        "longitude": 18.0686
    })

    assert response.status_code == 201
    data = response.json()

    # Verify Atlas classification was applied
    assert data['category'] == 'weapons'
    assert data['severity'] == 5
    assert data['atlas_threat_id'] is not None
```

### 3. End-to-End Tests
1. Create incident in Halo mobile app
2. Verify Atlas classification in Halo backend
3. Validate incident appears in Atlas intelligence DB
4. Check cross-product pattern detection
5. Test feedback loop (user validation → Atlas training)

---

## 📅 Implementation Timeline

### Week 3: Halo Integration

**Day 15-16: Atlas Client Library**
- [ ] Create `atlas_client.py` with all methods
- [ ] Add error handling and retry logic
- [ ] Write unit tests for Atlas client
- [ ] Document API usage

**Day 17-18: Refactor Halo Backend**
- [ ] Update database schema (add Atlas columns)
- [ ] Refactor incident creation endpoint
- [ ] Refactor media analysis endpoint
- [ ] Update requirements.txt (remove heavy ML deps)

**Day 19-21: Halo Mobile Updates**
- [ ] Update mobile app to display Atlas classifications
- [ ] Add threat severity indicators
- [ ] Show nearby intelligence patterns
- [ ] Test on iOS and Android

---

## 🚨 Graceful Degradation Strategy

### If Atlas is Down:
1. **Incident Classification**: Use basic keyword-based local classifier
2. **Media Analysis**: Return "analysis unavailable" message
3. **Intelligence Patterns**: Return empty array
4. **Queue for Later**: Store requests locally, sync when Atlas returns

### Fallback Classifier:
```python
# halo/backend/services/fallback_classifier.py
def basic_classify(description: str) -> str:
    """Simple keyword-based fallback when Atlas is unavailable"""
    description_lower = description.lower()

    if any(kw in description_lower for kw in ['gun', 'shoot', 'weapon']):
        return 'weapons'
    elif any(kw in description_lower for kw in ['fight', 'attack', 'assault']):
        return 'violence'
    elif any(kw in description_lower for kw in ['theft', 'steal', 'rob']):
        return 'theft'
    else:
        return 'suspicious_activity'
```

---

## 💰 Cost Impact

### Before Integration (Current)
- Halo Backend Railway: $40/mo (with ML processing)
- Total: $40/mo

### After Integration
- Halo Backend Railway: $10/mo (lightweight, no ML)
- Atlas Intelligence: $50/mo (shared across all products)
- Halo Savings: **$30/mo**

### Shared Across Products
- Atlas $50/mo ÷ 3 products = ~$17/mo per product
- Net savings per product: ~$23/mo
- **Total infrastructure: $60/mo** (Halo + Atlas + Frontline + SAIT)

---

## 📊 Success Metrics

### Technical KPIs
- [ ] 95%+ of incidents classified by Atlas (5% fallback acceptable)
- [ ] <200ms average Atlas API response time
- [ ] 99.5% uptime for Atlas API
- [ ] 10%+ accuracy improvement over local classification

### Business KPIs
- [ ] 90% of Halo incidents enriched with Atlas intelligence
- [ ] 5+ cross-product correlations detected per week
- [ ] User satisfaction with new "intelligence patterns" feature
- [ ] $30/mo cost savings on Halo infrastructure

---

## ⚠️ Risks and Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Atlas downtime affects Halo** | Medium | High | Fallback classifier, queue requests |
| **API latency issues** | Medium | Medium | Aggressive caching, async processing |
| **Data privacy concerns** | Low | Critical | Only send anonymized data, clear docs |
| **Integration bugs** | High | Medium | Comprehensive testing, gradual rollout |

---

## 🔄 Rollout Strategy

### Phase 1: Canary Deployment (Week 3)
- Deploy Atlas integration to 10% of Halo users
- Monitor for errors and performance issues
- Collect feedback

### Phase 2: Gradual Rollout (Week 4)
- Increase to 50% of users
- Validate accuracy improvements
- Fix any discovered issues

### Phase 3: Full Deployment (Week 5)
- Roll out to 100% of users
- Remove old local ML code
- Monitor and optimize

---

## 📝 Next Steps

1. **Immediate (This Week)**
   - [ ] Review this integration plan with team
   - [ ] Finalize API contract between Halo and Atlas
   - [ ] Begin Atlas client library development

2. **Week 3**
   - [ ] Complete Halo backend refactoring
   - [ ] Update Halo mobile app
   - [ ] End-to-end integration testing

3. **Week 4**
   - [ ] Deploy to production (canary)
   - [ ] Monitor and iterate
   - [ ] Full rollout

---

**Document Status:** Draft v1.0
**Last Updated:** October 7, 2025
**Next Review:** Start of Week 3
