from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from database.connection import get_db
from database.models import Alert

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


def _serialize(a: Alert) -> dict:
    return {
        "id": a.id,
        "factory_id": a.factory_id,
        "priority": a.priority,
        "message": a.message,
        "triggered_at": a.triggered_at.isoformat() if a.triggered_at else None,
        "ack_at": a.ack_at.isoformat() if a.ack_at else None,
        "is_acknowledged": a.ack_at is not None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("")
async def get_alerts(
    factory_id: Optional[int] = Query(None),
    is_acknowledged: Optional[bool] = Query(None),
    limit: int = Query(50, le=200),
    cursor: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    q = select(Alert).order_by(desc(Alert.id)).limit(limit)
    if factory_id is not None:
        q = q.where(Alert.factory_id == factory_id)
    if is_acknowledged is False:
        q = q.where(Alert.ack_at.is_(None))
    elif is_acknowledged is True:
        q = q.where(Alert.ack_at.isnot(None))
    if cursor is not None:
        q = q.where(Alert.id < cursor)

    result = await db.execute(q)
    rows = result.scalars().all()
    return {"success": True, "data": [_serialize(r) for r in rows]}


@router.post("/ack-all")
async def ack_all_alerts(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import update
    await db.execute(
        update(Alert)
        .where(Alert.ack_at.is_(None))
        .values(ack_at=datetime.now(timezone.utc))
    )
    await db.commit()
    return {"success": True}


@router.patch("/{alert_id}/ack")
async def ack_alert(alert_id: int, db: AsyncSession = Depends(get_db)):
    alert = await db.get(Alert, alert_id)
    if alert is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.ack_at = datetime.now(timezone.utc)
    await db.commit()
    return {"success": True, "data": _serialize(alert)}