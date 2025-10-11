"""
Configuration settings for Atlas Intelligence
"""

import os
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings"""

    # Application
    VERSION: str = "0.1.0"
    ATLAS_ENV: str = Field(default="development", env="ATLAS_ENV")
    DEBUG: bool = Field(default=True, env="DEBUG")
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")

    # Server
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8001, env="PORT")

    # Database (optional - can run without persistence)
    DATABASE_URL: str = Field(default="", env="DATABASE_URL")
    POSTGRES_HOST: str = Field(default="localhost", env="POSTGRES_HOST")
    POSTGRES_PORT: int = Field(default=5432, env="POSTGRES_PORT")
    POSTGRES_DB: str = Field(default="atlas_intelligence", env="POSTGRES_DB")
    POSTGRES_USER: str = Field(default="atlas_user", env="POSTGRES_USER")
    POSTGRES_PASSWORD: str = Field(default="password", env="POSTGRES_PASSWORD")

    # Redis (optional)
    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    REDIS_HOST: str = Field(default="localhost", env="REDIS_HOST")
    REDIS_PORT: int = Field(default=6379, env="REDIS_PORT")

    # Model Storage
    MODEL_STORAGE_PATH: str = Field(default="/app/models", env="MODEL_STORAGE_PATH")
    MODEL_CACHE_SIZE_MB: int = Field(default=500, env="MODEL_CACHE_SIZE_MB")

    # API Configuration
    MAX_MEDIA_SIZE_MB: int = Field(default=50, env="MAX_MEDIA_SIZE_MB")
    MAX_REQUEST_TIMEOUT_SEC: int = Field(default=30, env="MAX_REQUEST_TIMEOUT_SEC")
    RATE_LIMIT_PER_MINUTE: int = Field(default=100, env="RATE_LIMIT_PER_MINUTE")

    # CORS
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        env="CORS_ORIGINS"
    )

    # Product API Keys (optional - can generate defaults)
    API_KEY_HALO: str = Field(default="dev-halo-key", env="API_KEY_HALO")
    API_KEY_FRONTLINE: str = Field(default="dev-frontline-key", env="API_KEY_FRONTLINE")
    API_KEY_SAIT: str = Field(default="dev-sait-key", env="API_KEY_SAIT")
    JWT_SECRET_KEY: str = Field(default="dev-secret-change-in-production", env="JWT_SECRET_KEY")

    # Webhooks
    HALO_WEBHOOK_URL: str = Field(default="", env="HALO_WEBHOOK_URL")
    FRONTLINE_WEBHOOK_URL: str = Field(default="", env="FRONTLINE_WEBHOOK_URL")
    SAIT_WEBHOOK_URL: str = Field(default="", env="SAIT_WEBHOOK_URL")

    # Monitoring
    PROMETHEUS_ENABLED: bool = Field(default=True, env="PROMETHEUS_ENABLED")
    PROMETHEUS_PORT: int = Field(default=9090, env="PROMETHEUS_PORT")

    # Training
    TRAINING_DATA_PATH: str = Field(default="/app/training_data", env="TRAINING_DATA_PATH")
    MIN_TRAINING_SAMPLES: int = Field(default=100, env="MIN_TRAINING_SAMPLES")
    RETRAINING_SCHEDULE: str = Field(default="0 2 * * *", env="RETRAINING_SCHEDULE")

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"  # Allow extra environment variables


# Singleton settings instance
settings = Settings()
