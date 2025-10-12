#!/usr/bin/env python3
"""
Drop broken tables from Railway PostgreSQL database
"""
import asyncio
import os
import asyncpg

async def main():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        print("Please provide it: DATABASE_URL='postgres://...' python drop_tables.py")
        return 1

    # Fix postgres:// to postgresql://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    print(f"🔄 Connecting to database...")

    try:
        # Connect directly with asyncpg
        conn = await asyncpg.connect(database_url)

        print("✅ Connected to database")
        print("🔄 Dropping broken tables...")

        # Drop tables
        await conn.execute("DROP TABLE IF EXISTS incidents CASCADE;")
        await conn.execute("DROP TABLE IF EXISTS intelligence_patterns CASCADE;")
        await conn.execute("DROP TABLE IF EXISTS training_samples CASCADE;")
        await conn.execute("DROP TABLE IF EXISTS model_registry CASCADE;")
        await conn.execute("DROP TABLE IF EXISTS threat_intelligence CASCADE;")

        print("✅ Tables dropped successfully!")
        print("📋 Next: Restart Atlas Intelligence service to recreate tables")

        await conn.close()
        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    exit(asyncio.run(main()))
