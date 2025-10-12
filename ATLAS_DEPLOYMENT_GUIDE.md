# Atlas Intelligence - Railway Deployment Guide

## Zero-Redeployment Model Updates 🚀

This architecture allows you to update AI models **without pushing new code to Railway**.

---

## Initial Setup (One Time)

### 1. Choose S3-Compatible Storage

**Recommended: DigitalOcean Spaces** ($5/mo for 250GB)
- Create Space at https://cloud.digitalocean.com/spaces
- Note: Endpoint URL (e.g., `https://nyc3.digitaloceanspaces.com`)
- Generate API key (Access Key + Secret Key)

**Alternatives:**
- AWS S3 (more expensive, simpler setup)
- Cloudflare R2 (free tier, good for caching)
- MinIO (self-hosted)

### 2. Upload Initial Models to S3

Structure:
```
atlas-models/  (bucket name)
├── models/
│   ├── yolov8m/
│   │   ├── latest/
│   │   │   └── yolov8m.pt
│   │   ├── v2.0.0/
│   │   │   └── yolov8m.pt
│   │   └── metadata.json
│   └── sait_audio_classifier/
│       ├── latest/
│       │   └── sait_audio_classifier.pth
│       └── metadata.json
```

**Using AWS CLI:**
```bash
# Install AWS CLI
brew install awscli  # or: pip install awscli

# Configure for DigitalOcean Spaces
aws configure set aws_access_key_id YOUR_ACCESS_KEY
aws configure set aws_secret_access_key YOUR_SECRET_KEY
aws configure set default.region us-east-1

# Upload models
aws s3 cp yolov8m.pt s3://atlas-models/models/yolov8m/latest/ \
  --endpoint-url https://nyc3.digitaloceanspaces.com

aws s3 cp yolov8m.pt s3://atlas-models/models/yolov8m/v2.0.0/ \
  --endpoint-url https://nyc3.digitaloceanspaces.com
```

### 3. Configure Railway Environment Variables

In Railway dashboard → Variables:

```bash
# Required
MODEL_STORAGE_TYPE=s3
S3_BUCKET=atlas-models
S3_ACCESS_KEY=your_spaces_access_key
S3_SECRET_KEY=your_spaces_secret_key
S3_ENDPOINT_URL=https://nyc3.digitaloceanspaces.com

# Admin API (generate secure token)
ADMIN_TOKEN=your_secure_random_token_here

# Database
DATABASE_URL=postgresql://...  (Railway auto-provides)

# Optional
ATLAS_ENV=production
LOG_LEVEL=INFO
```

**Generate secure admin token:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 4. Deploy to Railway

```bash
# First deployment
git add .
git commit -m "Add S3 model storage and admin API"
git push railway main
```

---

## Updating Models (NO Code Redeployment!)

### Option A: Via Admin API (Recommended)

1. **Train new model locally**
2. **Upload to S3:**
   ```bash
   # Upload new version
   aws s3 cp yolov8m_new.pt s3://atlas-models/models/yolov8m/v2.1.0/yolov8m.pt \
     --endpoint-url https://nyc3.digitaloceanspaces.com
   
   # Update "latest"
   aws s3 cp yolov8m_new.pt s3://atlas-models/models/yolov8m/latest/yolov8m.pt \
     --endpoint-url https://nyc3.digitaloceanspaces.com
   ```

3. **Hot-reload via API:**
   ```bash
   curl -X POST https://atlas-intelligence.up.railway.app/api/v1/admin/reload-models \
     -H "Authorization: Bearer $ADMIN_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"model_type": "visual_detector", "version": "latest", "force_download": true}'
   ```

4. **Done!** New model is active in ~30 seconds.

### Option B: Via Railway Restart

1. Upload new model to S3 (same as above)
2. In Railway dashboard: Click "Restart" on your service
3. Service pulls latest models on startup

---

## Admin API Endpoints

### Reload Models
```bash
POST /api/v1/admin/reload-models
Authorization: Bearer YOUR_ADMIN_TOKEN

{
  "model_type": "visual_detector",  // or "audio_classifier", "threat_classifier", "all"
  "version": "latest",  // or "v2.1.0"
  "force_download": true
}
```

### List Model Versions
```bash
GET /api/v1/admin/models/versions/yolov8m
Authorization: Bearer YOUR_ADMIN_TOKEN

Response:
{
  "model_name": "yolov8m",
  "versions": ["v2.1.0", "v2.0.0", "v1.5.0"],
  "latest": "v2.1.0"
}
```

### Get Model Metadata
```bash
GET /api/v1/admin/models/metadata/yolov8m
Authorization: Bearer YOUR_ADMIN_TOKEN

Response:
{
  "version": "v2.1.0",
  "uploaded_at": "2025-10-07T20:00:00Z",
  "accuracy": 0.92,
  "file_size_mb": 49.7,
  "sha256": "abc123..."
}
```

### Clear Cache (Force Re-download)
```bash
POST /api/v1/admin/cache/clear
Authorization: Bearer YOUR_ADMIN_TOKEN
```

---

## Model Update Workflow

### Scenario 1: Improve YOLOv8 Accuracy

```bash
# 1. Train custom YOLOv8 with weapon detection
python train_yolo.py --data weapons.yaml --epochs 100

# 2. Upload to S3
aws s3 cp runs/train/weights/best.pt \
  s3://atlas-models/models/yolov8m/v2.1.0-weapons/yolov8m.pt \
  --endpoint-url https://nyc3.digitaloceanspaces.com

# 3. Hot-reload
curl -X POST https://atlas.railway.app/api/v1/admin/reload-models \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"model_type": "visual_detector", "version": "v2.1.0-weapons"}'
```

### Scenario 2: SAIT Audio Model Update

```bash
# 1. Train improved audio classifier
python train_sait_audio.py --data field_recordings/

# 2. Upload new version
aws s3 cp production_model_v2.pth \
  s3://atlas-models/models/sait_audio_classifier/v2.0.0/sait_audio_classifier.pth \
  --endpoint-url https://nyc3.digitaloceanspaces.com

# 3. Hot-reload
curl -X POST https://atlas.railway.app/api/v1/admin/reload-models \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"model_type": "audio_classifier", "version": "v2.0.0"}'
```

---

## Cost Optimization

**DigitalOcean Spaces Pricing:**
- $5/mo for 250GB storage
- $0.01/GB for bandwidth over 1TB

**Typical Usage:**
- 3 models x 50MB = 150MB
- 1000 downloads/month = 150GB bandwidth
- **Total: $5/mo**

**Railway Pricing:**
- Free tier: $5/mo credit
- Pro: $20/mo + usage
- Models on S3 = no Railway storage costs

---

## Troubleshooting

### Models not loading from S3
```bash
# Check S3 connectivity
curl -X GET https://atlas.railway.app/api/v1/admin/health \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Check logs in Railway dashboard
# Look for: "S3 connection successful" or error messages
```

### Force re-download
```bash
# Clear cache and reload
curl -X POST https://atlas.railway.app/api/v1/admin/cache/clear \
  -H "Authorization: Bearer $ADMIN_TOKEN"

curl -X POST https://atlas.railway.app/api/v1/admin/reload-models \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"model_type": "all", "force_download": true}'
```

### Rollback to previous version
```bash
# Just reload older version
curl -X POST https://atlas.railway.app/api/v1/admin/reload-models \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"model_type": "visual_detector", "version": "v2.0.0"}'
```

---

## When You MUST Redeploy Code

Only redeploy Railway when:
- Adding new API endpoints
- Changing business logic
- Updating dependencies (requirements.txt)
- Fixing bugs in application code

**Never need to redeploy for:**
- Model improvements ✅
- Changing model architectures (if weights compatible) ✅
- Adding new threat categories (update JSON in S3) ✅
- Adjusting confidence thresholds (update config in S3) ✅

---

## Summary

**With this architecture:**
- Upload model → API call → Active in 30 seconds
- No git commits, no Railway builds, no downtime
- Version control for models
- Instant rollbacks
- Perfect for rapid iteration

**Total setup time:** ~30 minutes
**Time saved per model update:** 15-20 minutes (no build/deploy wait)
