#!/usr/bin/env python3
"""
Run Alembic migrations for Atlas Intelligence
"""
import os
import sys
from alembic.config import Config
from alembic import command

def run_migrations():
    """Run all pending migrations"""
    print("🔄 Running database migrations...")

    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)

    # Fix postgres:// to postgresql:// for SQLAlchemy
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    # Create Alembic config
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "database/migrations")
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    try:
        # Run migrations
        command.upgrade(alembic_cfg, "head")
        print("✅ Database migrations completed successfully")
        return 0
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(run_migrations())
