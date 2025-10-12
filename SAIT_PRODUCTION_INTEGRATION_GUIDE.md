# SAIT_01 → Atlas Intelligence Production Integration

**Date:** October 9, 2025  
**Status:** Ready for Implementation  
**Atlas Production URL:** https://atlas-intelligence-production-fa0e.up.railway.app

---

## 🎯 Overview

SAIT_01 tactical audio devices are **already architected** for Atlas Intelligence integration. This guide shows you how to update the firmware to use the production Atlas URL.

### Key Principle: Edge-First, Cloud-Augmented
- ✅ SAIT runs TinyML **on-device** (primary)
- ✅ Atlas provides **cloud verification** (secondary, only when needed)
- ✅ No network required for high-confidence detections
- ✅ Battery life: 1.9 years continuous operation

---

## 🏗️ Architecture (Already Implemented)

```
┌─────────────────────────────────────────────────────────┐
│         SAIT_01 EDGE DEVICE (nRF5340)                   │
│                                                          │
│  TinyML Audio Classifier (Primary)                      │
│  • 30-class threat taxonomy                             │
│  • <100ms latency                                        │
│  • Confidence threshold: 0.85                            │
│                                                          │
│  Decision Logic:                                         │
│  ├─ High confidence (>0.85): IMMEDIATE local alert     │
│  ├─ Medium (0.5-0.85): Request cloud verification      │
│  └─ Low (<0.5): Local only, log                         │
└─────────────────────────────────────────────────────────┘
                         ▲
                         │ BLE Mesh / LoRa
                         │ (only when needed)
                         ▼
┌─────────────────────────────────────────────────────────┐
│   ATLAS INTELLIGENCE (Production)                       │
│   https://atlas-intelligence-production-fa0e.up.railway.app │
│                                                          │
│  Available Services:                                     │
│  ✅ POST /api/v1/sait/verify - Cloud verification       │
│  ✅ GET  /api/v1/sait/models/latest - OTA updates       │
│  ✅ GET  /api/v1/sait/models/{version}/download         │
│  ✅ POST /api/v1/sait/telemetry - Device health         │
│  ✅ POST /api/v1/sait/feedback - Training data          │
│  ✅ GET  /api/v1/sait/devices/{id}/status               │
└─────────────────────────────────────────────────────────┘
```

---

## 🔧 Required Firmware Updates

### 1. Update Cloud Endpoint URL

**File:** `sait_01_firmware/src/config.h` or equivalent

**Change:**
```c
// OLD (development)
#define ATLAS_CLOUD_URL "http://localhost:8001"

// NEW (production)
#define ATLAS_CLOUD_URL "https://atlas-intelligence-production-fa0e.up.railway.app"
```

### 2. Update API Endpoints

**Verification Endpoint:**
```c
// Edge detection verification
#define VERIFY_ENDPOINT "/api/v1/sait/verify"

// Full URL: https://atlas-intelligence-production-fa0e.up.railway.app/api/v1/sait/verify
```

**OTA Update Endpoint:**
```c
// Model version check
#define OTA_CHECK_ENDPOINT "/api/v1/sait/models/latest"

// Model download
#define OTA_DOWNLOAD_ENDPOINT "/api/v1/sait/models/%s/download"  // %s = version
```

**Telemetry Endpoint:**
```c
// Device health reporting
#define TELEMETRY_ENDPOINT "/api/v1/sait/telemetry"
```

### 3. Add Retry Logic (Recommended)

```c
// Network retry configuration
#define MAX_CLOUD_RETRIES 3
#define RETRY_DELAY_MS 1000  // 1 second between retries
#define REQUEST_TIMEOUT_MS 5000  // 5 second timeout

// Exponential backoff for retries
void cloud_request_with_retry(const char* endpoint, const char* payload) {
    int attempt = 0;
    int delay = RETRY_DELAY_MS;
    
    while (attempt < MAX_CLOUD_RETRIES) {
        int result = http_post(ATLAS_CLOUD_URL, endpoint, payload);
        
        if (result == HTTP_OK) {
            return;  // Success
        }
        
        attempt++;
        k_sleep(K_MSEC(delay));
        delay *= 2;  // Exponential backoff
    }
    
    // All retries failed - log and continue with edge-only mode
    LOG_WRN("Cloud verification unavailable, using edge detection only");
}
```

---

## 📡 API Integration Examples

### Example 1: Edge Detection Verification

**Scenario:** SAIT device detects "explosion_small" with 67% confidence (< 0.85 threshold)

**Request:**
```json
POST https://atlas-intelligence-production-fa0e.up.railway.app/api/v1/sait/verify
Content-Type: application/json

{
  "device_id": "sait_device_001",
  "edge_class_id": 5,
  "edge_class_name": "explosion_small",
  "edge_confidence": 0.67,
  "timestamp": "2025-10-09T12:00:00Z",
  "location": {
    "lat": 59.3293,
    "lon": 18.0686
  },
  "audio_base64": "<base64-encoded-audio-sample>"
}
```

**Response:**
```json
{
  "verified": true,
  "edge_confidence": 0.67,
  "cloud_confidence": 0.89,
  "edge_class": 5,
  "cloud_class": 5,
  "action": "cloud_verified",
  "final_category": "explosion_small",
  "recommendations": [
    "Alert confirmed by cloud",
    "High confidence - recommend immediate response"
  ],
  "processing_time_ms": 145
}
```

### Example 2: OTA Model Update Check

**Request:**
```json
GET https://atlas-intelligence-production-fa0e.up.railway.app/api/v1/sait/models/latest
```

**Response:**
```json
{
  "model_version": "v2.1.0",
  "model_type": "sait_audio_classifier",
  "architecture": "tinyml_conv1d",
  "num_classes": 30,
  "input_dim": 16000,
  "format": "tflite_micro",
  "accuracy": 0.94,
  "size_kb": 185,
  "deployed_at": "2025-10-09T10:00:00Z",
  "compatible_devices": ["nrf5340", "nrf9160"],
  "download_url": "/api/v1/sait/models/v2.1.0/download",
  "checksum": "sha256:abc123..."
}
```

### Example 3: Device Telemetry

**Request:**
```json
POST https://atlas-intelligence-production-fa0e.up.railway.app/api/v1/sait/telemetry
Content-Type: application/json

{
  "device_id": "sait_device_001",
  "firmware_version": "1.5.0",
  "model_version": "v2.0.0",
  "battery_voltage": 3.6,
  "uptime_seconds": 86400,
  "detections_count": 42,
  "cloud_requests": 7,
  "location": {
    "lat": 59.3293,
    "lon": 18.0686
  },
  "timestamp": "2025-10-09T12:00:00Z"
}
```

---

## ✅ Pre-Deployment Testing

### Test 1: Health Check
```bash
curl https://atlas-intelligence-production-fa0e.up.railway.app/health
```

**Expected:**
```json
{
  "status": "healthy",
  "services": {
    "threat_classifier": "operational",
    "visual_detector": "operational",
    "audio_classifier": "operational"
  }
}
```

### Test 2: SAIT Verify Endpoint
```bash
curl -X POST https://atlas-intelligence-production-fa0e.up.railway.app/api/v1/sait/verify \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "test_device",
    "edge_class_id": 0,
    "edge_class_name": "small_arms_fire",
    "edge_confidence": 0.75,
    "timestamp": "2025-10-09T12:00:00Z"
  }'
```

### Test 3: Model Metadata
```bash
curl https://atlas-intelligence-production-fa0e.up.railway.app/api/v1/sait/models/latest
```

---

## 📋 Deployment Checklist

### Firmware Updates
- [ ] Update `ATLAS_CLOUD_URL` to production URL
- [ ] Update API endpoint constants
- [ ] Add retry logic with exponential backoff
- [ ] Add request timeout handling
- [ ] Test OTA update flow
- [ ] Test cloud verification flow
- [ ] Test graceful degradation (offline mode)

### Testing
- [ ] Test high-confidence edge detection (>0.85) - should NOT call cloud
- [ ] Test medium-confidence detection (0.5-0.85) - SHOULD call cloud
- [ ] Test low-confidence detection (<0.5) - local only
- [ ] Test network failure scenarios
- [ ] Test OTA model update process
- [ ] Measure latency (edge vs cloud)
- [ ] Monitor battery impact of cloud requests

### Documentation
- [ ] Update deployment docs with production URL
- [ ] Document field deployment procedure
- [ ] Create troubleshooting guide
- [ ] Document expected latencies

---

## 📊 Expected Performance

### Edge Detection (No Cloud)
- **Latency:** <100ms
- **Accuracy:** ~89% (TinyML model)
- **Battery Impact:** Minimal (1.9 years continuous)
- **Network:** Not required

### Cloud Verification (When Needed)
- **Latency:** 300-500ms (includes network)
- **Accuracy:** ~94% (larger cloud model)
- **Battery Impact:** ~10% more per verification
- **Network:** Required (BLE Mesh → Gateway → Atlas)

### Network Failure Handling
- **Behavior:** Graceful degradation to edge-only mode
- **Alert:** Local BLE mesh alert still works
- **Logging:** Queue telemetry for later sync

---

## 🔐 Security Considerations

### TLS/HTTPS
- ✅ Atlas production uses HTTPS (TLS 1.2+)
- ✅ Certificate validation required in firmware
- ✅ Railway provides valid SSL certificate

### Authentication
- Optional: Add device API keys for production
- Current: Open API (rate-limited at 100 req/min)
- Future: Device-specific JWT tokens

### Data Privacy
- Audio samples sent to cloud are NOT stored permanently
- Only used for verification, then discarded
- Aggregated statistics only for training

---

## 🚀 Deployment Steps

### Step 1: Update Firmware
1. Clone SAIT firmware repository
2. Update configuration with production URLs
3. Add retry logic
4. Build firmware with updated configuration
5. Test on development device

### Step 2: Flash Development Device
1. Flash updated firmware to test device
2. Monitor serial logs for cloud connectivity
3. Trigger test detections at various confidence levels
4. Verify cloud requests are successful

### Step 3: Field Testing
1. Deploy 2-3 devices in controlled environment
2. Monitor telemetry data in Atlas
3. Validate detection accuracy
4. Measure battery impact over 48 hours

### Step 4: Production Rollout
1. OTA update to all field devices (if supported)
2. Or flash devices before deployment
3. Monitor Atlas telemetry dashboard
4. Adjust confidence thresholds if needed

---

## 📞 Troubleshooting

### Device Can't Connect to Atlas

**Check:**
```bash
# From gateway or device with network
ping atlas-intelligence-production-fa0e.up.railway.app

# Test HTTPS connection
curl https://atlas-intelligence-production-fa0e.up.railway.app/health
```

**Solutions:**
- Verify gateway has internet connectivity
- Check firewall rules (allow HTTPS port 443)
- Verify DNS resolution
- Check Atlas service status

### Cloud Verification Failing

**Check:**
- Audio encoding format (16kHz, 16-bit PCM)
- Base64 encoding correct
- Request payload size (<1MB recommended)
- Network timeout settings (increase if needed)

**Debug:**
```bash
# Test with sample audio
curl -X POST https://atlas-intelligence-production-fa0e.up.railway.app/api/v1/sait/verify \
  -H "Content-Type: application/json" \
  -d @test_payload.json
```

### OTA Updates Not Working

**Check:**
- Model download URL accessible
- Checksum validation passing
- Sufficient flash storage on device
- Network stability during download

---

## 📚 Additional Resources

### Atlas Intelligence Documentation
- API Docs: https://atlas-intelligence-production-fa0e.up.railway.app/docs
- Health Check: https://atlas-intelligence-production-fa0e.up.railway.app/health

### SAIT Documentation
- Architecture: `/Users/timothyaikenhead/Desktop/atlas-intelligence/SAIT_INTEGRATION.md`
- Threat Taxonomy: 30-class system (detailed in SAIT_INTEGRATION.md)

### Support
- Atlas Issues: Check Railway logs
- SAIT Firmware: Local repository

---

## 🎯 Success Criteria

- [ ] SAIT devices successfully connect to production Atlas
- [ ] High-confidence detections work without cloud (edge-only)
- [ ] Medium-confidence detections verified by cloud (<500ms)
- [ ] Network failures gracefully degrade to edge-only
- [ ] OTA model updates working
- [ ] Telemetry data flowing to Atlas
- [ ] Battery life remains >1.5 years with cloud features
- [ ] Cross-product correlation functional (SAIT + Halo + Frontline)

---

**Status:** ✅ Atlas Production Ready  
**Next Step:** Update SAIT firmware with production URL  
**Estimated Time:** 2-4 hours for firmware update + testing  

Generated: 2025-10-09
