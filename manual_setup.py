#!/usr/bin/env python3
"""
Manual setup script to initialize database and collect data
Run this locally with DATABASE_URL from Railway
"""
import asyncio
import os
import sys
import asyncpg
import httpx
from datetime import datetime

async def main():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        print("\nUsage:")
        print('  export DATABASE_URL="postgresql://..."')
        print("  python manual_setup.py")
        return 1

    # Fix postgres:// to postgresql://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    print("🔄 Connecting to database...")

    try:
        conn = await asyncpg.connect(database_url)
        print("✅ Connected to database")

        # Step 1: Drop existing tables
        print("\n🔄 Dropping existing tables...")
        await conn.execute("DROP TABLE IF EXISTS incidents CASCADE;")
        await conn.execute("DROP TABLE IF EXISTS intelligence_patterns CASCADE;")
        await conn.execute("DROP TABLE IF EXISTS training_samples CASCADE;")
        await conn.execute("DROP TABLE IF EXISTS model_registry CASCADE;")
        await conn.execute("DROP TABLE IF EXISTS threat_intelligence CASCADE;")
        print("✅ Tables dropped")

        # Step 2: Create incidents table (without PostGIS)
        print("\n🔄 Creating incidents table...")
        await conn.execute("""
            CREATE TABLE incidents (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                external_id VARCHAR(200) NOT NULL,
                source VARCHAR(50) NOT NULL,
                incident_type VARCHAR(100) NOT NULL,
                summary TEXT,
                location_name VARCHAR(200),
                latitude FLOAT NOT NULL,
                longitude FLOAT NOT NULL,
                occurred_at TIMESTAMP NOT NULL,
                url TEXT,
                severity INTEGER CHECK (severity BETWEEN 1 AND 5),
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP,
                CONSTRAINT uq_incident_external_id_source UNIQUE (external_id, source)
            );
        """)
        await conn.execute("CREATE INDEX idx_incident_occurred_at ON incidents (occurred_at);")
        await conn.execute("CREATE INDEX idx_incident_source ON incidents (source);")
        await conn.execute("CREATE INDEX idx_incident_severity ON incidents (severity);")
        print("✅ Incidents table created")

        # Step 3: Fetch data from polisen.se
        print("\n🔄 Fetching incidents from polisen.se...")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get("https://polisen.se/api/events")
            response.raise_for_status()
            events = response.json()

        print(f"✅ Fetched {len(events)} events from polisen.se")

        # Step 4: Insert incidents
        print("\n🔄 Inserting incidents into database...")
        stored_count = 0

        for event in events:
            try:
                # Parse GPS coordinates
                latitude = 59.3293  # Default Stockholm
                longitude = 18.0686

                if event.get("location", {}).get("gps"):
                    gps_parts = event["location"]["gps"].split(",")
                    if len(gps_parts) == 2:
                        latitude = float(gps_parts[0].strip())
                        longitude = float(gps_parts[1].strip())

                # Parse datetime
                occurred_at = datetime.now()
                if event.get("datetime"):
                    try:
                        occurred_at = datetime.fromisoformat(
                            event["datetime"].replace("Z", "+00:00")
                        )
                    except:
                        pass

                # Estimate severity
                incident_type = event.get("type", "unknown")
                severity_map = {
                    "Mord": 5, "Dråp": 5, "Skottlossning": 5,
                    "Rån": 4, "Misshandel": 3, "Stöld": 2,
                    "Trafikolycka": 2, "Övrigt": 1
                }
                severity = severity_map.get(incident_type, 2)

                # Insert
                await conn.execute("""
                    INSERT INTO incidents (
                        external_id, source, incident_type, summary, location_name,
                        latitude, longitude, occurred_at, url, severity, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (external_id, source) DO UPDATE SET
                        summary = EXCLUDED.summary,
                        updated_at = NOW()
                """,
                    str(event.get("id", "")),
                    "polisen",
                    incident_type,
                    event.get("summary", ""),
                    event.get("location", {}).get("name", ""),
                    latitude,
                    longitude,
                    occurred_at,
                    event.get("url", ""),
                    severity,
                    datetime.now()
                )
                stored_count += 1

            except Exception as e:
                print(f"  ⚠️ Failed to process event {event.get('id')}: {e}")
                continue

        print(f"✅ Inserted {stored_count} incidents into database")

        # Step 5: Verify
        count = await conn.fetchval("SELECT COUNT(*) FROM incidents;")
        print(f"\n📊 Total incidents in database: {count}")

        await conn.close()
        print("\n✅ Setup complete!")
        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
