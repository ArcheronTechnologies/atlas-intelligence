"""
Data API for Atlas Intelligence
Serves incident data collected from Swedish sources to product APIs
"""

import logging
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Query, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, or_
from sqlalchemy.sql import func

from database.database import get_database
from database.models import Incident
from api.rate_limits import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data", tags=["Data API"])


class IncidentResponse(BaseModel):
    """Single incident response"""
    id: str
    external_id: str
    source: str
    incident_type: str
    summary: str
    location_name: str
    latitude: float
    longitude: float
    occurred_at: datetime
    severity: int
    url: Optional[str] = None


class IncidentsListResponse(BaseModel):
    """List of incidents response"""
    total: int
    page: int
    page_size: int
    incidents: List[IncidentResponse]


@router.get("/incidents", response_model=IncidentsListResponse)
@limiter.limit("100/minute")
async def get_incidents(
    request: Request,
    lat: Optional[float] = Query(None, description="Latitude for radius search"),
    lon: Optional[float] = Query(None, description="Longitude for radius search"),
    radius_km: Optional[float] = Query(None, description="Search radius in kilometers", ge=0.1, le=100),
    hours: Optional[int] = Query(None, description="Get incidents from last N hours", ge=1, le=168),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    source: Optional[str] = Query(None, description="Filter by source (e.g., 'polisen')"),
    min_severity: Optional[int] = Query(None, description="Minimum severity (1-5)", ge=1, le=5)
):
    """
    Get incidents collected by Atlas Intelligence

    This endpoint serves incident data to Halo and other products.
    Data is collected from Swedish police (polisen.se) and other sources.
    """
    try:
        db = await get_database()

        # Build query
        query = select(Incident)

        # Time filter
        if hours:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            query = query.where(Incident.occurred_at >= cutoff_time)

        # Source filter
        if source:
            query = query.where(Incident.source == source)

        # Severity filter
        if min_severity:
            query = query.where(Incident.severity >= min_severity)

        # Radius filter (PostGIS)
        if lat is not None and lon is not None and radius_km:
            # ST_DWithin uses meters
            query = query.where(
                func.ST_DWithin(
                    Incident.location,
                    func.ST_MakePoint(lon, lat),
                    radius_km * 1000  # Convert km to meters
                )
            )

        # Count total
        async with db.session_factory() as session:
            count_query = select(func.count()).select_from(query.subquery())
            result = await session.execute(count_query)
            total = result.scalar()

            # Pagination
            offset = (page - 1) * page_size
            query = query.order_by(Incident.occurred_at.desc())
            query = query.offset(offset).limit(page_size)

            # Execute
            result = await session.execute(query)
            incidents = result.scalars().all()

            # Format response
            incident_responses = [
                IncidentResponse(
                    id=str(inc.id),
                    external_id=inc.external_id,
                    source=inc.source,
                    incident_type=inc.incident_type,
                    summary=inc.summary,
                    location_name=inc.location_name,
                    latitude=inc.latitude,
                    longitude=inc.longitude,
                    occurred_at=inc.occurred_at,
                    severity=inc.severity,
                    url=inc.url
                )
                for inc in incidents
            ]

            return IncidentsListResponse(
                total=total,
                page=page,
                page_size=page_size,
                incidents=incident_responses
            )

    except Exception as e:
        logger.error(f"Error fetching incidents: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch incidents")


@router.get("/incidents/recent", response_model=IncidentsListResponse)
@limiter.limit("100/minute")
async def get_recent_incidents(
    request: Request,
    hours: int = Query(24, description="Get incidents from last N hours", ge=1, le=168),
    page_size: int = Query(100, ge=1, le=500)
):
    """
    Get recent incidents (convenience endpoint for Halo)

    Returns incidents from the last N hours, most recent first.
    """
    return await get_incidents(
        request=request,
        hours=hours,
        page=1,
        page_size=page_size
    )


@router.post("/collection/trigger")
@limiter.limit("10/hour")
async def trigger_collection(request: Request):
    """
    Trigger immediate data collection (public endpoint for testing)

    Collects incident data from polisen.se and stores it in the database.
    """
    try:
        from services.data_collector import PolisenCollector

        logger.info("🔄 Triggering data collection...")

        collector = PolisenCollector()
        result = await collector.collect()

        logger.info(f"✅ Collection completed: {result}")

        return {
            "success": result.get("success", False),
            "records_collected": result.get("records", 0),
            "message": f"Collected {result.get('records', 0)} incidents from polisen.se",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Collection trigger failed: {e}")
        raise HTTPException(status_code=500, detail=f"Collection failed: {str(e)}")


@router.get("/collection/status")
@limiter.limit("30/minute")
async def get_collection_status(request: Request):
    """
    Get data collection service status

    Returns information about the ongoing data collection from Swedish sources.
    """
    try:
        from services.data_collector import get_data_collection_service

        service = await get_data_collection_service()
        status = service.get_status()

        return {
            "collection_service": status,
            "sources": {
                "polisen": {
                    "enabled": True,
                    "url": "https://polisen.se/api/events",
                    "interval_minutes": status["interval_minutes"]
                }
            }
        }

    except Exception as e:
        logger.error(f"Error getting collection status: {e}")
        return {
            "collection_service": {
                "running": False,
                "error": str(e)
            }
        }
