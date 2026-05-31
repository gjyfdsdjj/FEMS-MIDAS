from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.connection import get_db
from database.models import Job

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


def _serialize(j: Job) -> dict:
    quantity = j.quantity or 0
    produced = j.produced_units or 0
    return {
        "id": j.id,
        "factory_id": j.factory_id,
        "quantity": quantity,
        "target_units": j.target_units,
        "status": j.status,
        "deadline_at": j.deadline_at.isoformat() if j.deadline_at else None,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "produced_units": produced,
        "remaining_units": max(0, quantity - produced),
        "progress_rate": round(produced / quantity, 4) if quantity > 0 else 0.0,
        "dynamic_scheduling_enabled": j.dynamic_scheduling_enabled,
        "daily_shipment_hour": j.daily_shipment_hour,
    }


@router.get("")
async def get_jobs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).order_by(Job.id.desc()))
    rows = result.scalars().all()
    return {"success": True, "data": [_serialize(r) for r in rows]}


@router.get("/current")
async def get_current_job(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Job)
        .where(Job.status.in_(["pending", "in_progress"]))
        .order_by(Job.created_at.desc())
        .limit(1)
    )
    job = result.scalars().first()
    if job is None:
        raise HTTPException(status_code=404, detail="No active job")
    return {"success": True, "data": _serialize(job)}