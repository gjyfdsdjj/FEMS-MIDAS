from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from database.models import ControlLog


async def log_control_action(
    db: AsyncSession,
    *,
    factory_id: int,
    node_id: str,
    action: str,
    value: float | None = None,
    reason: str | None = None,
    requested_by: str = "streamlit",
    result: str | None = None,
) -> None:
    db.add(ControlLog(
        factory_id=factory_id,
        node_id=node_id,
        action=action,
        value=value,
        reason=reason,
        requested_by=requested_by,
        result=result,
        issued_at=datetime.now(timezone.utc),
    ))
    await db.commit()


async def get_control_logs(
    db: AsyncSession,
    factory_id: int | None = None,
    limit: int = 50,
    cursor: int | None = None,
) -> list[dict]:
    q = select(ControlLog).order_by(desc(ControlLog.issued_at)).limit(limit)
    if factory_id is not None:
        q = q.where(ControlLog.factory_id == factory_id)
    if cursor is not None:
        q = q.where(ControlLog.id < cursor)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "factory_id": r.factory_id,
            "node_id": r.node_id,
            "action": r.action,
            "value": r.value,
            "reason": r.reason,
            "requested_by": r.requested_by,
            "result": r.result,
            "issued_at": r.issued_at.isoformat() if r.issued_at else None,
        }
        for r in rows
    ]