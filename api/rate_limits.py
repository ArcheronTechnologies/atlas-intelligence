"""
Rate Limiting Configuration for Atlas Intelligence APIs
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Initialize limiter
limiter = Limiter(key_func=get_remote_address)

# Rate limit definitions by endpoint type
RATE_LIMITS = {
    # Heavy ML inference endpoints
    "classify": "30/minute",      # Threat classification
    "analyze": "20/minute",        # Media analysis (heavy)

    # Product-specific APIs
    "halo": "60/minute",           # Halo incident management
    "sait": "100/minute",          # SAIT devices (higher limit for edge devices)
    "frontline": "60/minute",      # Frontline security

    # Core services
    "intelligence": "40/minute",   # Intelligence queries
    "training": "10/minute",       # Model training (heavy)

    # Public endpoints
    "info": "100/minute",          # Info/health/docs
    "models": "50/minute",         # Model metadata
}

def get_rate_limit(endpoint_type: str) -> str:
    """Get rate limit string for endpoint type"""
    return RATE_LIMITS.get(endpoint_type, "50/minute")  # Default fallback
