from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from database.connection import get_db
from services import operations_service

router = APIRouter(prefix="/api/v1/operations", tags=["operations"])


@router.get("/sensor-reliability/{factory_id}")
async def get_sensor_reliability(
    factory_id: int,
    hours: int = Query(default=24),
    db: AsyncSession = Depends(get_db),
):
    return await operations_service.sensor_reliability(db, factory_id, hours)


@router.get("/temperature-stability/{factory_id}")
async def get_temperature_stability(
    factory_id: int,
    hours: int = Query(default=24),
    db: AsyncSession = Depends(get_db),
):
    return await operations_service.temperature_stability(db, factory_id, hours)


@router.get("/target-adherence/{factory_id}")
async def get_target_adherence(
    factory_id: int,
    hours: int = Query(default=24),
    tolerance: float = Query(default=2.0),
    db: AsyncSession = Depends(get_db),
):
    return await operations_service.target_temp_adherence(db, factory_id, hours, tolerance)


@router.get("/efficiency-score/{factory_id}")
async def get_efficiency_score(
    factory_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await operations_service.operational_efficiency_score(db, factory_id)


@router.get("/inventory/{factory_id}")
async def get_inventory(
    factory_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await operations_service.inventory_capacity(db, factory_id)


@router.get("/job-compliance")
async def get_job_compliance(db: AsyncSession = Depends(get_db)):
    return await operations_service.job_deadline_compliance(db)


@router.get("/door-events/{factory_id}")
async def get_door_events(
    factory_id: int,
    hours: int = Query(default=24),
    db: AsyncSession = Depends(get_db),
):
    return await operations_service.door_event_analysis(db, factory_id, hours)


@router.get("/cooling-cycles/{factory_id}")
async def get_cooling_cycles(
    factory_id: int,
    hours: int = Query(default=24),
    db: AsyncSession = Depends(get_db),
):
    return await operations_service.cooling_cycle_analysis(db, factory_id, hours)


@router.get("/human-presence/{factory_id}")
async def get_human_presence(
    factory_id: int,
    hours: int = Query(default=24),
    db: AsyncSession = Depends(get_db),
):
    return await operations_service.human_presence_analysis(db, factory_id, hours)


@router.get("/maintenance/{factory_id}")
async def get_maintenance_recommendation(
    factory_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await operations_service.maintenance_recommendation(db, factory_id)
