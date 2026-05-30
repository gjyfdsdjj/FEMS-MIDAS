from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.connection import get_db
from database.models import Factory

router = APIRouter(prefix="/api/v1/factories", tags=["factories"])


def _serialize(f: Factory) -> dict:
    return {
        "factory_id": f.factory_id,
        "name": f.name,
        "status": f.status,
        "current_temp": f.current_temp,
        "current_humidity": f.current_humidity,
        "last_seen_at": f.last_seen_at.isoformat() if f.last_seen_at else None,
        "max_quantity": f.max_quantity,
        "is_door_open": f.is_door_open,
        "door_open_count": f.door_open_count,
        "node_id": f.node_id,
        "manual_stop": f.manual_stop,
        "target_temp_c": f.target_temp_c,
        "current_stock_units": f.current_stock_units,
        "control_mode": f.control_mode,
    }


@router.get("")
async def get_factories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Factory).order_by(Factory.factory_id))
    rows = result.scalars().all()
    return {"success": True, "data": [_serialize(r) for r in rows]}


@router.get("/{factory_id}")
async def get_factory(factory_id: int, db: AsyncSession = Depends(get_db)):
    factory = await db.get(Factory, factory_id)
    if factory is None:
        raise HTTPException(status_code=404, detail="Factory not found")
    return {"success": True, "data": _serialize(factory)}