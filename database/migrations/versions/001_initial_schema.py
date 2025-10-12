"""Initial schema

Revision ID: 001
Revises:
Create Date: 2025-10-07

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
# import geoalchemy2  # Disabled: PostGIS not available on Railway

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # PostGIS not available on Railway - using lat/lon columns instead
    # op.execute('CREATE EXTENSION IF NOT EXISTS postgis')

    # Create threat_intelligence table
    op.create_table(
        'threat_intelligence',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('threat_category', sa.String(50), nullable=False),
        sa.Column('threat_subcategory', sa.String(50)),
        sa.Column('severity', sa.Integer(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('halo_incident_type', sa.String(50)),
        sa.Column('frontline_object_class', sa.String(50)),
        sa.Column('sait_threat_code', sa.String(50)),
        sa.Column('source_product', sa.String(20), nullable=False),
        sa.Column('source_event_id', postgresql.UUID(as_uuid=True)),
        sa.Column('latitude', sa.Float()),
        sa.Column('longitude', sa.Float()),
        # sa.Column('location', geoalchemy2.Geography('POINT', srid=4326)),  # Disabled: PostGIS not available
        sa.Column('occurred_at', sa.DateTime(), nullable=False),
        sa.Column('validated', sa.Boolean(), default=False),
        sa.Column('validation_source', sa.String(20)),
        sa.Column('validation_timestamp', sa.DateTime()),
        sa.Column('correlated_events', postgresql.JSONB()),
        sa.Column('multi_modal_confidence', sa.Float()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('NOW()')),
        sa.CheckConstraint('severity BETWEEN 1 AND 5', name='ck_severity_range'),
        sa.CheckConstraint('confidence_score BETWEEN 0 AND 1', name='ck_confidence_range'),
    )

    # Create indexes for threat_intelligence
    # op.create_index('idx_threat_location', 'threat_intelligence', ['location'], postgresql_using='gist')  # Disabled: PostGIS not available
    op.create_index('idx_threat_time', 'threat_intelligence', ['occurred_at'])
    op.create_index('idx_threat_category', 'threat_intelligence', ['threat_category'])
    op.create_index('idx_threat_source', 'threat_intelligence', ['source_product'])
    op.create_index('idx_threat_lat_lon', 'threat_intelligence', ['latitude', 'longitude'])

    # Create model_registry table
    op.create_table(
        'model_registry',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('model_name', sa.String(100), nullable=False),
        sa.Column('model_version', sa.String(20), nullable=False),
        sa.Column('model_type', sa.String(50), nullable=False),
        sa.Column('model_path', sa.Text(), nullable=False),
        sa.Column('accuracy_halo', sa.Float()),
        sa.Column('accuracy_frontline', sa.Float()),
        sa.Column('accuracy_sait', sa.Float()),
        sa.Column('overall_accuracy', sa.Float()),
        sa.Column('training_data_sources', postgresql.JSONB()),
        sa.Column('training_samples_count', sa.Integer()),
        sa.Column('training_duration_seconds', sa.Integer()),
        sa.Column('hyperparameters', postgresql.JSONB()),
        sa.Column('active', sa.Boolean(), default=False),
        sa.Column('deployed_at', sa.DateTime()),
        sa.Column('deprecated_at', sa.DateTime()),
        sa.Column('trained_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()')),
        sa.UniqueConstraint('model_name', 'model_version', name='uq_model_name_version'),
    )

    op.create_index('idx_model_type_active', 'model_registry', ['model_type', 'active'])

    # Create training_samples table
    op.create_table(
        'training_samples',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('source_product', sa.String(20), nullable=False),
        sa.Column('source_event_id', postgresql.UUID(as_uuid=True)),
        sa.Column('sample_type', sa.String(50), nullable=False),
        sa.Column('media_url', sa.Text()),
        sa.Column('media_metadata', postgresql.JSONB()),
        sa.Column('true_category', sa.String(50), nullable=False),
        sa.Column('predicted_category', sa.String(50)),
        sa.Column('correction_applied', sa.Boolean(), default=False),
        sa.Column('confidence_score', sa.Float()),
        sa.Column('used_in_training', sa.Boolean(), default=False),
        sa.Column('training_runs', postgresql.JSONB()),
        sa.Column('data_quality_score', sa.Float()),
        sa.Column('validated', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()')),
    )

    op.create_index('idx_training_source', 'training_samples', ['source_product'])
    op.create_index('idx_training_type', 'training_samples', ['sample_type'])
    op.create_index('idx_training_category', 'training_samples', ['true_category'])
    op.create_index('idx_training_unused', 'training_samples', ['used_in_training'],
                   postgresql_where=sa.text('NOT used_in_training'))

    # Create intelligence_patterns table
    op.create_table(
        'intelligence_patterns',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('pattern_type', sa.String(50), nullable=False),
        sa.Column('pattern_name', sa.String(200)),
        sa.Column('threat_categories', postgresql.ARRAY(sa.String(100))),
        sa.Column('frequency_count', sa.Integer()),
        sa.Column('frequency_trend', sa.String(20)),
        sa.Column('sources', postgresql.JSONB(), nullable=False),
        sa.Column('cross_product_correlation', sa.Float()),
        sa.Column('center_latitude', sa.Float()),
        sa.Column('center_longitude', sa.Float()),
        # sa.Column('location_center', geoalchemy2.Geography('POINT', srid=4326)),  # Disabled: PostGIS not available
        sa.Column('location_radius_meters', sa.Float()),
        sa.Column('time_window_start', sa.DateTime()),
        sa.Column('time_window_end', sa.DateTime()),
        sa.Column('confidence_score', sa.Float()),
        sa.Column('statistical_significance', sa.Float()),
        sa.Column('discovered_at', sa.DateTime(), server_default=sa.text('NOW()')),
        sa.Column('last_updated', sa.DateTime(), server_default=sa.text('NOW()')),
        sa.Column('active', sa.Boolean(), default=True),
    )

    # op.create_index('idx_pattern_location', 'intelligence_patterns', ['location_center'], postgresql_using='gist')  # Disabled: PostGIS not available
    op.create_index('idx_pattern_time', 'intelligence_patterns', ['time_window_start', 'time_window_end'])
    op.create_index('idx_pattern_lat_lon', 'intelligence_patterns', ['center_latitude', 'center_longitude'])


def downgrade():
    op.drop_table('intelligence_patterns')
    op.drop_table('training_samples')
    op.drop_table('model_registry')
    op.drop_table('threat_intelligence')
    # op.execute('DROP EXTENSION IF EXISTS postgis')  # PostGIS not used
