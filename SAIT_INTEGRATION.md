# SAIT_01 ↔ Atlas Intelligence Integration

**Date:** October 7, 2025
**Status:** Implemented (Week 1 Days 5-7 complete)
**Integration Type:** Edge + Cloud Hybrid

---

## 📋 Overview

This document describes how SAIT_01 tactical audio intelligence devices integrate with Atlas Intelligence for cloud verification, OTA updates, and cross-device intelligence.

### Key Principle: **Edge-First, Cloud-Augmented**

- **SAIT_01 devices run TinyML models ON-DEVICE** (nRF5340 embedded)
- **Atlas provides cloud services** to complement edge inference
- **NOT a replacement** - it's an enhancement!

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│              SAIT_01 EDGE DEVICE (nRF5340)              │
├─────────────────────────────────────────────────────────┤
│  TinyML Audio Classifier (Primary)                      │
│  • 30-class threat taxonomy                             │
│  • <100ms latency                                        │
│  • No network required                                   │
│  • Battery: 1.9 years continuous                         │
│                                                          │
│  Decision Logic:                                         │
│  ├─ High confidence (>0.85): Report immediately         │
│  ├─ Medium confidence (0.5-0.85): Request cloud verify  │
│  └─ Low confidence (<0.5): Local only, log              │
└─────────────────────────────────────────────────────────┘
                         ▲
                         │ BLE Mesh / LoRa
                         │ (only when needed)
                         ▼
┌─────────────────────────────────────────────────────────┐
│             ATLAS INTELLIGENCE (Cloud)                   │
├─────────────────────────────────────────────────────────┤
│  Audio Classifier Service (Secondary)                   │
│  • Same 30-class taxonomy                               │
│  • Higher accuracy model (more parameters)               │
│  • Cross-device correlation                              │
│  • Continuous learning from field data                   │
│                                                          │
│  Services Provided:                                      │
│  ├─ Cloud verification for uncertain detections         │
│  ├─ OTA model update distribution                       │
│  ├─ Multi-device intelligence aggregation                │
│  ├─ Model training from field data                       │
│  └─ Cross-product threat correlation                     │
└─────────────────────────────────────────────────────────┘
```

---

## 🎯 SAIT_01 30-Class Threat Taxonomy

Both edge and cloud use the same taxonomy for consistency:

### **Immediate Lethal Threats** (Classes 0-5)
- `0`: small_arms_fire (gunshots)
- `1`: artillery_fire
- `2`: mortar_fire
- `3`: rocket_launch
- `4`: explosion_large
- `5`: explosion_small

### **Direct Combat Vehicles** (Classes 6-11)
- `6`: tank_movement
- `7`: apc_movement (armored personnel carrier)
- `8`: truck_convoy
- `9`: helicopter_rotor
- `10`: jet_aircraft
- `11`: propeller_aircraft

### **Human Activity / Surveillance** (Classes 12-15)
- `12`: radio_chatter
- `13`: shouting_commands
- `14`: footsteps_marching
- `15`: equipment_clanking

### **Mechanical Sounds** (Classes 16-23)
- `16`: engine_idle
- `17`: engine_revving
- `18`: door_slam
- `19`: metal_impact
- `20`: glass_breaking
- `21`: alarm_siren
- `22`: whistle_signal
- `23`: crowd_noise

### **Environmental** (Classes 24-26)
- `24`: construction_noise
- `25`: ambient_quiet
- `26`: wind_noise

### **Aerial Threats** (Classes 27-29)
- `27`: drone_acoustic
- `28`: helicopter_military
- `29`: aerial_background

---

## 🔄 Integration Workflows

### **Workflow 1: High-Confidence Edge Detection**

```
1. SAIT device detects "small_arms_fire" with 92% confidence
   ├─ Confidence > 85% threshold
   └─> IMMEDIATE local alert via BLE mesh

2. Device reports to Atlas (async, non-blocking)
   └─> POST /api/v1/intelligence/events
       {
         "source": "sait_device_001",
         "class_id": 0,
         "class_name": "small_arms_fire",
         "confidence": 0.92,
         "location": {"lat": 59.33, "lon": 18.07},
         "timestamp": "2025-10-07T12:00:00Z"
       }

3. Atlas logs event and checks for correlations
   ├─ Looks for nearby Frontline detections (muzzle flash)
   ├─ Checks Halo for recent incident reports
   └─> Creates high-confidence threat event if correlated

4. NO cloud verification needed - edge was confident!
```

### **Workflow 2: Uncertain Edge Detection (Cloud Verification)**

```
1. SAIT device detects "explosion_small" with 67% confidence
   ├─ Confidence between 0.5-0.85 (uncertain)
   └─> Request cloud verification

2. Device sends audio sample to Atlas
   └─> POST /api/v1/verify/edge-detection
       {
         "edge_class_id": 5,
         "edge_confidence": 0.67,
         "audio_data": <base64-encoded audio>
       }

3. Atlas re-analyzes with larger cloud model
   ├─ Extracts mel-spectrogram features
   ├─ Runs through cloud AudioClassifierModel (512-dim hidden)
   └─> Returns: class_id=5, confidence=0.89

4. Atlas confirms detection
   └─> Response: {
         "verified": true,
         "cloud_confidence": 0.89,
         "action": "cloud_verified",
         "final_category": "weapons"
       }

5. SAIT device upgrades alert to high confidence
```

### **Workflow 3: OTA Model Update**

```
1. Atlas trains improved model from field data
   ├─ Aggregates 10,000 samples from all SAIT devices
   ├─ Retrains with better accuracy: 87% → 92%
   └─> Compresses to TFLite for edge deployment

2. SAIT device requests model update (periodic check)
   └─> GET /api/v1/models/sait/latest

3. Atlas responds with model metadata
   └─> {
         "version": "1.1.0",
         "accuracy": 0.92,
         "size_kb": 186,
         "format": "tflite",
         "download_url": "/api/v1/models/sait/v1.1.0/download"
       }

4. SAIT device downloads and validates new model
   ├─ Downloads model package
   ├─ Validates checksum
   ├─ Tests on validation samples
   └─> Activates if validation passes

5. Device reports deployment success to Atlas
```

---

## 🔧 Atlas Audio Classifier Implementation

### **File:** `services/audio_classifier.py` (525 lines)

Key components:

#### **AudioClassifierModel**
```python
class AudioClassifierModel(nn.Module):
    """Multi-scale audio classification model"""

    def __init__(self, num_classes=30, input_dim=128):
        # 3-layer fully connected network
        # Input: 128-dim mel-spectrogram features
        # Hidden: 256 → 512 → 256
        # Output: 30 classes
```

#### **AudioClassifier Service**
```python
class AudioClassifier:
    """Cloud audio classification service for SAIT integration"""

    async def classify_audio(audio_data, sample_rate):
        # Extract mel-spectrogram features
        # Run inference
        # Map SAIT class → Atlas threat category
        # Return classification + recommendations

    async def verify_edge_detection(sait_detection, audio_data):
        # Compare edge vs cloud predictions
        # Return verification result

    async def get_ota_model_package(target_format='tflite'):
        # Prepare model for OTA distribution
        # Convert to edge-compatible format
```

---

## 📊 SAIT → Atlas Threat Mapping

| SAIT Classes | Atlas Category | Severity | Priority |
|--------------|----------------|----------|----------|
| 0-5 (weapons) | `weapons` | 5 | IMMEDIATE_LETHAL |
| 13-15, 20, 23 (violence) | `violence` | 4 | DIRECT_COMBAT |
| 6-8, 27-28 (military) | `vehicle_crime` | 4 | DIRECT_COMBAT |
| 9-11, 16-17 (civilian) | `vehicle_crime` | 2 | SURVEILLANCE |
| 12, 21-24 (noise) | `disturbance` | 2 | SURVEILLANCE |
| 15, 18-19 (equipment) | `suspicious_activity` | 2 | SURVEILLANCE |
| 25-26, 29 (ambient) | `background` | 1 | NON_THREAT |

---

## 🔐 Security & Privacy

### **Data Transmission**
- Audio only sent to cloud for uncertain detections (< 85% confidence)
- TLS encryption in transit
- No PII in audio metadata
- Audio deleted after 30 days

### **Model Security**
- OTA updates signed with cryptographic keys
- Device validates model integrity before deployment
- Rollback capability if new model performs worse

### **Edge Autonomy**
- SAIT devices operate fully offline
- Cloud unavailability = degraded mode (edge-only)
- No single point of failure

---

## 📈 Performance Targets

### **Edge (SAIT Device)**
| Metric | Target | Actual |
|--------|--------|--------|
| Latency | <100ms | ~80ms |
| Accuracy | >85% | 87-92% |
| Battery Life | >1 year | 1.9 years |
| False Positive Rate | <5% | ~3% |

### **Cloud (Atlas)**
| Metric | Target | Actual |
|--------|--------|--------|
| Verification Accuracy | >90% | TBD (needs training) |
| Response Time | <500ms | TBD (needs profiling) |
| Uptime | 99.5% | TBD (not deployed) |

---

## 🚀 Deployment Status

### ✅ Completed
- [x] Audio classifier service (525 lines)
- [x] SAIT 30-class taxonomy mapped to Atlas
- [x] Cloud verification endpoint logic
- [x] OTA model distribution methods
- [x] Integration with media analyzer
- [x] Threat recommendations generator

### ⏳ Pending
- [ ] Train production cloud model (need field data)
- [ ] Convert PyTorch → TFLite for OTA
- [ ] Test with real SAIT devices
- [ ] Deploy to Railway
- [ ] Set up model registry database

---

## 🔄 Future Enhancements

### **Phase 1** (Week 2-3)
- Deploy Atlas to Railway
- Train cloud model on aggregated SAIT data
- Test OTA update workflow

### **Phase 2** (Week 4-5)
- Multi-modal correlation (audio + visual)
- Temporal threat tracking
- Swarm intelligence (multiple SAIT devices)

### **Phase 3** (Week 6+)
- Continuous learning pipeline
- Federated learning across devices
- Real-time threat mapping

---

## 📝 API Endpoints

### **POST /api/v1/verify/edge-detection**
Verify SAIT edge detection with cloud model

**Request:**
```json
{
  "edge_class_id": 0,
  "edge_confidence": 0.67,
  "audio_data": "<base64-encoded>"
}
```

**Response:**
```json
{
  "verified": true,
  "cloud_confidence": 0.89,
  "action": "cloud_verified",
  "final_category": "weapons"
}
```

### **GET /api/v1/models/sait/latest**
Get latest SAIT model for OTA update

**Response:**
```json
{
  "version": "1.0.0",
  "accuracy": 0.87,
  "size_kb": 186,
  "download_url": "/api/v1/models/sait/v1.0.0/download"
}
```

---

## 🎓 Lessons Learned

1. **Edge-first is critical** - Cloud augments, doesn't replace
2. **Consistent taxonomy** across edge/cloud prevents confusion
3. **Selective cloud verification** saves bandwidth and power
4. **OTA updates** enable continuous improvement without hardware changes

---

**Document Status:** Complete
**Last Updated:** October 7, 2025
**Implementation:** Week 1 Days 5-7 (complete)
**Next Steps:** Deploy to Railway, train cloud model
