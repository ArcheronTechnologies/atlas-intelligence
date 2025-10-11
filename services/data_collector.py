"""
Data collection service for Atlas Intelligence
Collects crime data from Swedish sources (polisen.se)
"""

import logging
import asyncio
import httpx
from typing import Dict
from datetime import datetime
from sqlalchemy.dialects.postgresql import insert
from geoalchemy2.elements import WKTElement

from database.database import get_database
from database.models import Incident

logger = logging.getLogger(__name__)


class PolisenCollector:
    """Collector for Swedish Police (Polisen.se) data"""

    def __init__(self):
        self.api_url = "https://polisen.se/api/events"
        self.source = "polisen"

    async def collect(self) -> Dict:
        """Collect incidents from Polisen.se API"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.api_url)
                response.raise_for_status()
                events = response.json()

            if not events:
                logger.info("No events returned from Polisen API")
                return {"success": True, "records": 0}

            db = await get_database()
            stored_count = 0

            async with db.session_factory() as session:
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

                        incident_data = {
                            "external_id": str(event.get("id", "")),
                            "source": self.source,
                            "incident_type": event.get("type", "unknown"),
                            "summary": event.get("summary", ""),
                            "location_name": event.get("location", {}).get("name", ""),
                            "latitude": latitude,
                            "longitude": longitude,
                            "location": WKTElement(f'POINT({longitude} {latitude})', srid=4326),
                            "occurred_at": occurred_at,
                            "url": event.get("url", ""),
                            "severity": self._estimate_severity(event.get("type", "")),
                            "created_at": datetime.now()
                        }

                        # Upsert (insert or update on conflict)
                        stmt = insert(Incident).values(**incident_data)
                        stmt = stmt.on_conflict_do_update(
                            index_elements=["external_id", "source"],
                            set_={
                                "summary": stmt.excluded.summary,
                                "updated_at": datetime.now()
                            }
                        )
                        await session.execute(stmt)
                        stored_count += 1

                    except Exception as e:
                        logger.error(f"Failed to process event {event.get('id')}: {e}", exc_info=True)
                        continue

                await session.commit()

            logger.info(f"✅ Collected {stored_count} incidents from Polisen.se (fetched {len(events)} total)")
            return {"success": True, "records": stored_count, "fetched": len(events)}

        except Exception as e:
            logger.error(f"Failed to collect from Polisen.se: {e}", exc_info=True)
            return {"success": False, "error": str(e), "records": 0}

    def _estimate_severity(self, incident_type: str) -> int:
        """Estimate severity (1-5) based on incident type"""
        severity_map = {
            "Mord": 5,
            "Dråp": 5,
            "Skottlossning": 5,
            "Bombhot": 5,
            "Sprängning": 5,
            "Misshandel": 4,
            "Rån": 4,
            "Våldtäkt": 5,
            "Inbrott": 3,
            "Trafikolycka": 3,
            "Stöld": 2,
            "Skadegörelse": 2,
            "Tillgrepp": 2,
        }

        for keyword, severity in severity_map.items():
            if keyword.lower() in incident_type.lower():
                return severity

        return 1


class DataCollectionService:
    """Service for continuous data collection"""

    def __init__(self, interval_minutes: int = 15):
        self.interval_minutes = interval_minutes
        self.is_running = False
        self.collection_task = None
        self.polisen_collector = PolisenCollector()
        self.total_collections = 0
        self.total_incidents = 0

    async def start(self):
        """Start continuous data collection"""
        if self.is_running:
            logger.warning("Data collection service already running")
            return

        self.is_running = True
        self.collection_task = asyncio.create_task(self._collection_loop())
        logger.info(f"🚀 Data collection service started (interval: {self.interval_minutes}min)")

    async def stop(self):
        """Stop data collection"""
        self.is_running = False
        if self.collection_task:
            self.collection_task.cancel()
            try:
                await self.collection_task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Data collection service stopped")

    async def _collection_loop(self):
        """Main collection loop"""
        while self.is_running:
            try:
                await self.collect_once()
                await asyncio.sleep(self.interval_minutes * 60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Collection loop error: {e}")
                await asyncio.sleep(60)

    async def collect_once(self) -> Dict:
        """Run one collection cycle"""
        logger.info("Starting data collection cycle...")
        start_time = datetime.now()

        result = await self.polisen_collector.collect()

        if result["success"]:
            self.total_collections += 1
            self.total_incidents += result["records"]

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Collection cycle complete: {result['records']} incidents in {duration:.1f}s")

        return result

    def get_status(self) -> Dict:
        """Get service status"""
        return {
            "running": self.is_running,
            "interval_minutes": self.interval_minutes,
            "total_collections": self.total_collections,
            "total_incidents": self.total_incidents
        }


# Singleton instance
_data_collection_service = None


async def get_data_collection_service() -> DataCollectionService:
    """Get or create data collection service"""
    global _data_collection_service
    if _data_collection_service is None:
        _data_collection_service = DataCollectionService()
    return _data_collection_service


async def start_data_collection():
    """Start data collection service"""
    service = await get_data_collection_service()
    await service.start()


async def stop_data_collection():
    """Stop data collection service"""
    global _data_collection_service
    if _data_collection_service:
        await _data_collection_service.stop()
