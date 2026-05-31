from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.connection import get_db
from database.models import Schedule

router = APIRouter(prefix="/api/v1/schedules", tags=["schedules"])


def _serialize(s: Schedule) -> dict:
    return {
        "id": s.id,
        "factory_id": s.factory_id,
        "target_temp": s.target_temp,
        "mode": s.mode,
        "start_at": s.start_at.isoformat() if s.start_at else None,
        "end_at": s.end_at.isoformat() if s.end_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("")
async def get_schedules(
    factory_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    q = (
        select(Schedule)
        .where(Schedule.end_at >= now)
        .order_by(Schedule.factory_id, Schedule.start_at)
    )
    if factory_id is not None:
        q = q.where(Schedule.factory_id == factory_id)

    result = await db.execute(q)
    rows = result.scalars().all()
    return {"success": True, "data": [_serialize(r) for r in rows]}