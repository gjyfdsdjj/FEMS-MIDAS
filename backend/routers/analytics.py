from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db
from services import analytics_service


router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/cooling-efficiency/{factory_id}")
async def get_cooling_efficiency(
    factory_id: int,
    hours: int = Query(default=24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.cooling_efficiency(db, factory_id, hours)


@router.get("/temperature-predict/{factory_id}")
async def get_temperature_prediction(
    factory_id: int,
    horizon_minutes: int = Query(default=60, ge=5, le=1440),
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.predict_temperature(db, factory_id, horizon_minutes)


@router.get("/anomalies/{factory_id}")
async def get_anomalies(
    factory_id: int,
    minutes: int = Query(default=5, ge=1, le=120),
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.detect_anomalies(db, factory_id, minutes)


@router.get("/cooling-load/{factory_id}")
async def get_cooling_load(
    factory_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.cooling_load(db, factory_id)
