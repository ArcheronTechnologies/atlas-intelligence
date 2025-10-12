# Atlas Intelligence - Pre-Deployment Improvements

## Completed Improvements

### 1. ✅ Upgraded to YOLOv8m
- Changed from YOLOv8n (nano) to YOLOv8m (medium)
- **Impact**: +5-10% accuracy
- **Trade-off**: ~25MB model, ~2x slower inference
- **Justification**: Better accuracy worth the speed trade-off for v0.1

### 2. ⚠️ Rate Limiting (In Progress)
- Added `slowapi` dependency
- Need to apply to all sensitive endpoints
- Prevents abuse and DDoS

### 3. ⚠️ Input Validation (TODO)
- Need Pydantic validators on all request models
- Sanitize file uploads
- Limit request sizes

## Remaining Critical Improvements

### Priority 1: SAIT Audio Model Fix
**Status**: BROKEN - Model weights don't match architecture
**Time**: 2-3 hours
**Options**:
1. **Quick**: Use placeholder with logging (document as "beta")
2. **Better**: Retrain model with correct architecture
3. **Best**: Import and convert existing SAIT model properly

**Recommendation**: Option 1 for v0.1, then option 3 post-launch

### Priority 2: Training Data Collection
**Status**: Database schema exists, endpoints don't collect data
**Time**: 1 hour
**Tasks**:
- Log all predictions to database
- Add feedback endpoints
- Store training samples

### Priority 3: Rate Limiting Implementation
**Status**: Library installed, not applied
**Time**: 30 minutes
**Apply to**:
- `/api/v1/classify/*` - 30 requests/minute per IP
- `/api/v1/analyze/*` - 20 requests/minute (heavier)
- `/api/v1/halo/*` - 60 requests/minute
- `/api/v1/sait/*` - 100 requests/minute (devices)

### Priority 4: Input Validation
**Status**: Basic Pydantic validation exists
**Time**: 1 hour
**Add**:
- File size limits (max 10MB images, 50MB video, 5MB audio)
- MIME type validation
- String length limits
- SQL injection prevention (already handled by asyncpg)
- XSS prevention on text fields

## Decision: Deploy Now or Improve First?

### Option A: Deploy As-Is
**Pros**:
- All tests passing (12/12)
- Core functionality works
- Can collect real data immediately

**Cons**:
- Audio model doesn't work with real audio (placeholder mode)
- No rate limiting (vulnerable to abuse)
- Missing training data collection

**Recommendation**: NO - Audio model and rate limiting are critical

### Option B: Quick Fixes Then Deploy (2-3 hours)
**Do**:
1. Add rate limiting (30 min)
2. Add input validation (1 hour)
3. Fix or document audio model as beta (1 hour)
4. Add basic training data logging (30 min)

**Recommendation**: YES - This gets us deploy-ready

### Option C: Full Improvements (1-2 days)
**Do**:
- Train proper threat classifier (ML model)
- Train fresh SAIT audio model
- Full model versioning system
- Comprehensive monitoring

**Recommendation**: NO - Do post-launch with real data

## Final Pre-Deployment Checklist

### Must-Do (Deploy Blockers):
- [ ] Add rate limiting to all endpoints
- [ ] Add file size validation
- [ ] Fix audio model OR add clear "beta" warnings
- [ ] Add request logging for analytics
- [ ] Test with production-like load

### Should-Do:
- [ ] Add model versioning table usage
- [ ] Implement feedback collection
- [ ] Add more comprehensive error messages
- [ ] Security headers (CORS, CSP, etc.)

### Can Wait:
- [ ] Train better threat classifier
- [ ] Fine-tune YOLOv8 on security dataset
- [ ] Retrain SAIT model properly
- [ ] A/B testing framework

## Timeline

**Now → 3 hours**: Priority fixes
**3 hours → Deploy**: Railway deployment
**Week 1-2 post-launch**: Collect data, monitor
**Week 3-4**: First model improvements with real data

## Recommendation

**Deploy after 3 hours of focused work**:
1. Rate limiting (30 min) ✅ Critical
2. Input validation (1 hour) ✅ Critical
3. Audio model fix/beta label (1 hour) ✅ Critical
4. Training data logging (30 min) ✅ Important

**Then**: Deploy, monitor, improve with real data

This gives us:
- Production-ready security
- Working core features
- Path to improvement with data
- Realistic v0.1 expectations
