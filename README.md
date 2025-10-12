# Atlas Intelligence Backbone

**Shared AI/ML infrastructure powering Halo, Frontline AI, and SAIT_01**

## Overview

Atlas Intelligence is a unified threat intelligence platform that provides:

- 🧠 **Threat Classification** - Multi-modal threat categorization across products
- 📸 **Media AI Analysis** - Photo, video, and audio threat detection
- 🎯 **Model Training** - Continuous improvement from aggregated data
- 📊 **Intelligence Patterns** - Cross-product threat correlation

## Architecture

```
Atlas Intelligence
├── Halo (Public Safety)          → Incident classification, media analysis
├── Frontline AI (Physical Sec.)  → Visual detection enrichment
└── SAIT_01 (Tactical Audio)      → Cloud-based audio analysis
```

## Quick Start

### Prerequisites
- Python 3.9+
- PostgreSQL 14+ with PostGIS
- Redis (for caching)

### Local Development

```bash
# Clone repository
git clone https://github.com/yourusername/atlas-intelligence.git
cd atlas-intelligence

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your database credentials

# Run migrations
alembic upgrade head

# Start server
python main.py
```

Server will be available at `http://localhost:8001`

API documentation: `http://localhost:8001/docs`

## API Endpoints

### Threat Classification
```bash
POST /api/v1/classify/threat
```

### Media Analysis
```bash
POST /api/v1/analyze/media
```

### Intelligence Patterns
```bash
GET /api/v1/intelligence/patterns
```

### Training & Feedback
```bash
POST /api/v1/training/feedback
POST /api/v1/training/retrain
```

## Deployment

### Railway (Production)

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link project
railway link

# Deploy
railway up
```

Estimated cost: ~$50/month

## Project Structure

```
atlas-intelligence/
├── api/                    # API endpoints
├── services/               # Core business logic
├── models/                 # ML model storage
├── database/               # Database models & migrations
├── config/                 # Configuration files
├── utils/                  # Shared utilities
├── tests/                  # Test suite
├── main.py                 # FastAPI application
└── requirements.txt        # Python dependencies
```

## Development

### Running Tests
```bash
pytest tests/ -v
```

### Code Style
```bash
# Format code
black .

# Lint
flake8 .

# Type checking
mypy .
```

### Database Migrations
```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Integration Guides

- [Halo Integration Guide](docs/integration/halo.md)
- [Frontline AI Integration Guide](docs/integration/frontline.md)
- [SAIT_01 Integration Guide](docs/integration/sait.md)

## Documentation

- [API Reference](docs/api/README.md)
- [Threat Taxonomy](docs/threat_taxonomy.md)
- [Architecture Overview](docs/architecture.md)
- [Model Training Guide](docs/training.md)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Security

For security issues, please email security@example.com instead of using the issue tracker.

## License

MIT License - see [LICENSE](LICENSE) for details

## Support

- Documentation: [docs.atlas-intelligence.com](https://docs.atlas-intelligence.com)
- Issues: [GitHub Issues](https://github.com/yourusername/atlas-intelligence/issues)
- Email: support@example.com

---

**Version:** 0.1.0
**Status:** Active Development
**Maintained by:** Timothy Aikenhead
