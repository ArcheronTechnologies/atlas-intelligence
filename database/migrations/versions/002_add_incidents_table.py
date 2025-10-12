"""Add incidents table

Revision ID: 002
Revises: 001
Create Date: 2025-10-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
# import geoalchemy2  # Disabled: PostGIS not available on Railway

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # Create incidents table
    op.create_table(
        'incidents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('external_id', sa.String(200), nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('incident_type', sa.String(100), nullable=False),
        sa.Column('summary', sa.Text()),
        sa.Column('location_name', sa.String(200)),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        # sa.Column('location', geoalchemy2.Geography('POINT', srid=4326)),  # Disabled: PostGIS not available
        sa.Column('occurred_at', sa.DateTime(), nullable=False),
        sa.Column('url', sa.Text()),
        sa.Column('severity', sa.Integer()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('NOW()')),
        sa.UniqueConstraint('external_id', 'source', name='uq_incident_external_id_source'),
        sa.CheckConstraint('severity BETWEEN 1 AND 5', name='ck_incident_severity_range'),
    )

    # Create indexes for incidents
    # op.create_index('idx_incident_location', 'incidents', ['location'], postgresql_using='gist')  # Disabled: PostGIS not available
    op.create_index('idx_incident_occurred_at', 'incidents', ['occurred_at'])
    op.create_index('idx_incident_source', 'incidents', ['source'])
    op.create_index('idx_incident_severity', 'incidents', ['severity'])
    op.create_index('idx_incident_lat_lon', 'incidents', ['latitude', 'longitude'])


def downgrade():
    op.drop_table('incidents')
