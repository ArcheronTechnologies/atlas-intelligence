# Atlas Intelligence Ecosystem - Directory Structure

**Last Updated:** October 7, 2025

---

## 📁 Desktop Directory Layout

```
/Users/timothyaikenhead/Desktop/
│
├── Halo/                                    # Public Safety App (formerly "Atlas-AI")
│   ├── backend/                             # FastAPI backend
│   │   ├── api/                            # API endpoints
│   │   ├── services/                       # Business logic
│   │   │   ├── atlas_client.py            # ← TO BE CREATED (Week 3)
│   │   │   ├── data_ingestion_service.py
│   │   │   ├── prediction_scheduler.py
│   │   │   └── push_notification_service.py
│   │   ├── database/                       # Halo operational data
│   │   └── main.py
│   │
│   ├── mobile/                             # React Native app
│   │   ├── app/
│   │   ├── components/
│   │   └── services/
│   │
│   └── .git/                               # Git: atlas-halo-backend
│
├── atlas-intelligence/                     # Atlas Intelligence Backbone (NEW)
│   ├── api/                                # 4 API routers
│   │   ├── inference_api.py               # /classify/threat
│   │   ├── media_api.py                   # /analyze/media
│   │   ├── training_api.py                # /training/*
│   │   └── intelligence_api.py            # /intelligence/*
│   │
│   ├── services/                           # Core AI services
│   │   ├── threat_classifier.py           # ✅ Working
│   │   ├── visual_detector.py             # ✅ YOLOv8 loaded
│   │   ├── media_analyzer.py              # ✅ Working
│   │   └── audio_classifier.py            # ⏳ To be created
│   │
│   ├── database/                           # Intelligence database
│   │   ├── models.py                      # 4 tables defined
│   │   └── database.py
│   │
│   ├── config/
│   │   ├── settings.py
│   │   └── threat_taxonomy.yaml           # ✅ Unified taxonomy
│   │
│   ├── models/
│   │   └── yolov8n.pt                     # ✅ 6.2MB model
│   │
│   ├── main.py                             # FastAPI app
│   ├── test_api.py                         # ✅ Test script
│   ├── requirements.txt
│   ├── HALO_INTEGRATION_PLAN.md           # ✅ 712 lines
│   └── .git/                               # Git: atlas-intelligence
│
├── SAIT_01 Firmware:Software/              # Tactical Audio Intelligence
│   ├── firmware/                           # nRF5340 embedded code
│   ├── training/                           # Audio ML training
│   ├── models/                             # TinyML models
│   └── docs/
│       ├── SAIT_01_BILL_OF_MATERIALS.md
│       ├── SAIT_01_Signal_Hopping_Report.md
│       └── SAIT_01_Dual_Stack_Mesh_Report.md
│
├── Atlas_Intelligence_Architecture_Plan.md # Master architecture (1,475 lines)
├── Atlas_Intelligence_Complete_Roadmap.md  # 6-week roadmap (877 lines)
└── Atlas_Session_Summary.md                # Progress tracker (462 lines)
```

---

## 🎯 Project Relationships

### Atlas Intelligence (Backbone)
- **Purpose:** Shared AI/ML infrastructure
- **Location:** `/Users/timothyaikenhead/Desktop/atlas-intelligence/`
- **Git Remote:** None yet (local only)
- **Status:** Week 1 Days 3-4 complete
- **API:** http://localhost:8001

### Halo (Public Safety)
- **Purpose:** Incident reporting and community safety
- **Location:** `/Users/timothyaikenhead/Desktop/Halo/`
- **Git Remote:** https://github.com/ArcheronTechnologies/atlas-halo-backend.git
- **Status:** Operational, needs Atlas integration (Week 3)
- **Rename:** Recently renamed from "Atlas-AI" to "Halo"

### SAIT_01 (Tactical Audio)
- **Purpose:** Battlefield audio threat detection
- **Location:** `/Users/timothyaikenhead/Desktop/SAIT_01 Firmware:Software/`
- **Status:** Hardware complete, needs cloud integration

---

## 🔗 Integration Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    ATLAS INTELLIGENCE                        │
│                  (Shared AI/ML Backbone)                     │
│                                                              │
│  API Gateway: http://localhost:8001                          │
│  • /api/v1/classify/threat                                   │
│  • /api/v1/analyze/media                                     │
│  • /api/v1/intelligence/patterns                             │
│  • /api/v1/training/feedback                                 │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ HTTP REST API
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│     HALO      │    │ FRONTLINE AI  │    │   SAIT_01     │
│               │    │               │    │               │
│ /Desktop/Halo/│    │ (Future)      │    │ /Desktop/     │
│               │    │               │    │ SAIT_01.../   │
└───────────────┘    └───────────────┘    └───────────────┘
```

---

## 📝 Important Notes

### Naming Convention
- **"Atlas Intelligence"** = The AI/ML backbone (this new project)
- **"Halo"** = The public safety app (formerly called "Atlas AI")
- **"Atlas"** alone typically refers to Atlas Intelligence

### Git Repositories
1. **atlas-intelligence** (local, no remote yet)
   - New project created this session
   - 5 commits so far

2. **Halo** (has remote: atlas-halo-backend)
   - Existing project with full history
   - To be integrated with Atlas in Week 3

### Path Updates Needed
When creating integration code, use these paths:
- Halo backend: `/Users/timothyaikenhead/Desktop/Halo/backend/`
- Atlas Intelligence: `/Users/timothyaikenhead/Desktop/atlas-intelligence/`
- SAIT_01: `/Users/timothyaikenhead/Desktop/SAIT_01 Firmware:Software/`

---

## ✅ Current Status

### Completed
- [x] Atlas Intelligence repository created
- [x] Atlas API operational (localhost:8001)
- [x] Threat classifier working
- [x] YOLOv8 visual detection loaded
- [x] Halo directory renamed (clarity)
- [x] Integration plan documented

### Next Steps (Week 1 Days 5-7)
- [ ] Extract SAIT audio classifier
- [ ] Test audio detection API
- [ ] Deploy Atlas to Railway

### Week 3: Integration
- [ ] Create `Halo/backend/services/atlas_client.py`
- [ ] Refactor Halo to use Atlas API
- [ ] Update Halo database schema
- [ ] End-to-end testing

---

**Document Status:** Living document
**Maintained by:** Atlas Intelligence development team
**Last verification:** October 7, 2025
