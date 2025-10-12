#!/usr/bin/env python3
"""
Enable PostGIS extension in Railway PostgreSQL database
"""
import asyncio
import os
import asyncpg

async def main():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        return 1

    # Fix postgres:// to postgresql://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    print(f"🔄 Connecting to database...")

    try:
        # Connect directly with asyncpg
        conn = await asyncpg.connect(database_url)

        print("✅ Connected to database")
        print("🔄 Enabling PostGIS extension...")

        # Enable PostGIS
        await conn.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        await conn.execute("CREATE EXTENSION IF NOT EXISTS postgis_topology;")

        print("✅ PostGIS extensions enabled successfully!")

        # Verify
        result = await conn.fetchval("SELECT PostGIS_version();")
        print(f"📍 PostGIS version: {result}")

        await conn.close()
        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    exit(asyncio.run(main()))
