"""
SQLAlchemy database models for Atlas Intelligence
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, Index, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base
# from geoalchemy2 import Geography  # Disabled: PostGIS not available on Railway

Base = declarative_base()


class Incident(Base):
    """Raw incident data collected from external sources (polisen.se, etc)"""
    __tablename__ = 'incidents'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # External source tracking
    external_id = Column(String(200), nullable=False)
    source = Column(String(50), nullable=False)

    # Incident details
    incident_type = Column(String(100), nullable=False)
    summary = Column(Text)
    location_name = Column(String(200))

    # Geospatial
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    # location = Column(Geography('POINT', srid=4326))  # Disabled: PostGIS not available on Railway

    # Temporal
    occurred_at = Column(DateTime, nullable=False)

    # Additional data
    url = Column(Text)
    severity = Column(Integer, CheckConstraint('severity BETWEEN 1 AND 5'))

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('external_id', 'source', name='uq_incident_external_id_source'),
        # Index('idx_incident_location', location, postgresql_using='gist'),  # Disabled: PostGIS not available
        Index('idx_incident_occurred_at', 'occurred_at'),
        Index('idx_incident_source', 'source'),
        Index('idx_incident_severity', 'severity'),
    )


class ThreatIntelligence(Base):
    """Shared threat intelligence across all products"""
    __tablename__ = 'threat_intelligence'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Unified classification
    threat_category = Column(String(50), nullable=False)
    threat_subcategory = Column(String(50))
    severity = Column(Integer, CheckConstraint('severity BETWEEN 1 AND 5'), nullable=False)
    confidence_score = Column(Float, CheckConstraint('confidence_score BETWEEN 0 AND 1'), nullable=False)

    # Multi-product mapping
    halo_incident_type = Column(String(50))
    frontline_object_class = Column(String(50))
    sait_threat_code = Column(String(50))

    # Source tracking
    source_product = Column(String(20), nullable=False)  # 'halo', 'frontline', 'sait'
    source_event_id = Column(UUID(as_uuid=True))

    # Spatial-temporal data
    latitude = Column(Float)
    longitude = Column(Float)
    # location = Column(Geography('POINT', srid=4326))  # Disabled: PostGIS not available on Railway
    occurred_at = Column(DateTime, nullable=False)

    # Validation & learning
    validated = Column(Boolean, default=False)
    validation_source = Column(String(20))
    validation_timestamp = Column(DateTime)

    # Correlation tracking
    correlated_events = Column(JSONB)
    multi_modal_confidence = Column(Float)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        # Index('idx_threat_location', location, postgresql_using='gist'),  # Disabled: PostGIS not available
        Index('idx_threat_time', 'occurred_at'),
        Index('idx_threat_category', 'threat_category'),
        Index('idx_threat_source', 'source_product'),
        Index('idx_threat_lat_lon', 'latitude', 'longitude'),
    )


class ModelRegistry(Base):
    """Model version control and performance tracking"""
    __tablename__ = 'model_registry'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Model identification
    model_name = Column(String(100), nullable=False)
    model_version = Column(String(20), nullable=False)
    model_type = Column(String(50), nullable=False)  # 'threat_classifier', 'visual_detector', etc.
    model_path = Column(Text, nullable=False)

    # Performance metrics (per product)
    accuracy_halo = Column(Float)
    accuracy_frontline = Column(Float)
    accuracy_sait = Column(Float)
    overall_accuracy = Column(Float)

    # Training metadata
    training_data_sources = Column(JSONB)
    training_samples_count = Column(Integer)
    training_duration_seconds = Column(Integer)
    hyperparameters = Column(JSONB)

    # Deployment status
    active = Column(Boolean, default=False)
    deployed_at = Column(DateTime)
    deprecated_at = Column(DateTime)

    # Timestamps
    trained_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('model_name', 'model_version', name='uq_model_name_version'),
        Index('idx_model_type_active', 'model_type', 'active'),
    )


class TrainingSample(Base):
    """Training data aggregated from all products"""
    __tablename__ = 'training_samples'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Source information
    source_product = Column(String(20), nullable=False)
    source_event_id = Column(UUID(as_uuid=True))
    sample_type = Column(String(50), nullable=False)  # 'visual', 'audio', 'text', 'multi_modal'

    # Media references
    media_url = Column(Text)
    media_metadata = Column(JSONB)

    # Labels & corrections
    true_category = Column(String(50), nullable=False)
    predicted_category = Column(String(50))
    correction_applied = Column(Boolean, default=False)
    confidence_score = Column(Float)

    # Training usage
    used_in_training = Column(Boolean, default=False)
    training_runs = Column(JSONB)  # List of model versions trained with this sample

    # Quality flags
    data_quality_score = Column(Float)
    validated = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_training_source', 'source_product'),
        Index('idx_training_type', 'sample_type'),
        Index('idx_training_category', 'true_category'),
        Index('idx_training_unused', 'used_in_training', postgresql_where='NOT used_in_training'),
    )


class IntelligencePattern(Base):
    """Cross-product intelligence patterns"""
    __tablename__ = 'intelligence_patterns'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Pattern identification
    pattern_type = Column(String(50), nullable=False)  # 'spatial_cluster', 'temporal_trend', 'correlation'
    pattern_name = Column(String(200))

    # Pattern details
    threat_categories = Column(JSONB, nullable=False)  # Array of related threat types
    frequency_count = Column(Integer)
    frequency_trend = Column(String(20))  # 'increasing', 'decreasing', 'stable'

    # Multi-product contribution
    sources = Column(JSONB, nullable=False)  # {"halo": 12, "frontline": 5, "sait": 2}
    cross_product_correlation = Column(Float)

    # Spatial-temporal scope
    center_latitude = Column(Float)
    center_longitude = Column(Float)
    # location_center = Column(Geography('POINT', srid=4326))  # Disabled: PostGIS not available on Railway
    location_radius_meters = Column(Float)
    time_window_start = Column(DateTime)
    time_window_end = Column(DateTime)

    # Significance
    confidence_score = Column(Float)
    statistical_significance = Column(Float)

    # Metadata
    discovered_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    active = Column(Boolean, default=True)

    __table_args__ = (
        # Index('idx_pattern_location', location_center, postgresql_using='gist'),  # Disabled: PostGIS not available
        Index('idx_pattern_time', 'time_window_start', 'time_window_end'),
        Index('idx_pattern_lat_lon', 'center_latitude', 'center_longitude'),
    )
