from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from database.connection import get_db
from services import energy_service

router = APIRouter(prefix="/api/v1/energy", tags=["energy"])


@router.get("/consumption")
async def get_consumption(
    factory_id: int = Query(...),
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
):
    return await energy_service.estimate_consumption(db, factory_id, hours)


@router.get("/savings")
async def get_savings(
    factory_id: int = Query(...),
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
):
    return await energy_service.estimate_savings(db, factory_id, hours)


@router.get("/peak")
async def get_peak(
    factory_id: int = Query(...),
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
):
    return await energy_service.peak_analysis(db, factory_id, hours)


@router.get("/carbon")
async def get_carbon(kwh: float = Query(..., gt=0)):
    return energy_service.carbon_emission(kwh)


@router.get("/summary")
async def get_summary(
    factory_id: int = Query(...),
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
):
    consumption = await energy_service.estimate_consumption(db, factory_id, hours)
    savings = await energy_service.estimate_savings(db, factory_id, hours)
    peak = await energy_service.peak_analysis(db, factory_id, hours)
    carbon = energy_service.carbon_emission(consumption["total_kwh"])
    return {
        "factory_id": factory_id,
        "period_hours": hours,
        "consumption": consumption,
        "savings": savings,
        "peak": peak,
        "carbon": carbon,
    }
