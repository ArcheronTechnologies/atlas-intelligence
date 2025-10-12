#!/usr/bin/env python3
"""
Manually trigger data collection from polisen.se
"""
import asyncio
import os
import sys

async def main():
    # Set DATABASE_URL if needed
    if not os.getenv("DATABASE_URL"):
        print("ERROR: DATABASE_URL environment variable not set")
        print("Usage: DATABASE_URL='<url>' python manual_collect.py")
        sys.exit(1)

    from services.data_collector import PolisenCollector

    print("🔄 Starting data collection from polisen.se...")

    collector = PolisenCollector()
    result = await collector.collect()

    print(f"\n✅ Collection complete!")
    print(f"   Success: {result.get('success')}")
    print(f"   Records: {result.get('records')}")
    if result.get('error'):
        print(f"   Error: {result.get('error')}")

if __name__ == "__main__":
    asyncio.run(main())
