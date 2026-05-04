from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db
from database.models import Factory, Schedule, SensorLog
from mqtt.status_store import status_store


router = APIRouter(prefix="/api/v1/readonly", tags=["readonly"])

TOKEN_FACTORY_MAP = {
    "rdonly_test_1": 1,
}


def _resolve_factory_id(token: str) -> int | None:
    if token in TOKEN_FACTORY_MAP:
        return TOKEN_FACTORY_MAP[token]

    for prefix in ("factory_", "factory-", "rdonly_test_"):
        if token.startswith(prefix):
            try:
                return int(token.removeprefix(prefix))
            except ValueError:
                return None
    return None


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _status_from_temp(temp: float | None, measured_at: datetime | None) -> str:
    if temp is None or measured_at is None:
        return "WAITING"

    now = datetime.now(timezone.utc)
    last_seen = measured_at if measured_at.tzinfo else measured_at.replace(tzinfo=timezone.utc)
    if (now - last_seen).total_seconds() > 30:
        return "WARNING"
    if temp < -24 or temp > -16:
        return "WARNING"
    return "NORMAL"


async def _latest_history(db: AsyncSession, factory_id: int, hours: int = 24) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(SensorLog.temperature_c, SensorLog.measured_at)
        .where(SensorLog.factory_id == factory_id)
        .where(SensorLog.measured_at >= since)
        .order_by(SensorLog.measured_at)
    )
    return [
        {
            "timestamp": _iso(row.measured_at),
            "temperature_c": float(row.temperature_c) if row.temperature_c is not None else None,
        }
        for row in result.all()
        if row.measured_at is not None
    ]


@router.get("/{token}")
async def get_readonly_factory_info(token: str, db: AsyncSession = Depends(get_db)):
    factory_id = _resolve_factory_id(token)
    if factory_id is None:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": {
                    "code": "NOT_FOUND",
                    "message": "readonly token not found",
                    "details": {},
                },
            },
        )

    factory = await db.get(Factory, factory_id)
    sensor_result = await db.execute(
        select(SensorLog)
        .where(SensorLog.factory_id == factory_id)
        .order_by(SensorLog.measured_at.desc(), SensorLog.id.desc())
        .limit(1)
    )
    latest_sensor = sensor_result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    current_schedule_result = await db.execute(
        select(Schedule)
        .where(Schedule.factory_id == factory_id)
        .where(Schedule.start_at <= now)
        .where(Schedule.end_at >= now)
        .order_by(Schedule.start_at)
        .limit(1)
    )
    current_schedule = current_schedule_result.scalar_one_or_none()

    next_schedule_result = await db.execute(
        select(Schedule)
        .where(Schedule.factory_id == factory_id)
        .where(Schedule.start_at > now)
        .order_by(Schedule.start_at)
        .limit(1)
    )
    next_schedule = next_schedule_result.scalar_one_or_none()

    temperature = (
        float(latest_sensor.temperature_c)
        if latest_sensor is not None and latest_sensor.temperature_c is not None
        else None
    )
    humidity = (
        float(latest_sensor.humidity_pct)
        if latest_sensor is not None and latest_sensor.humidity_pct is not None
        else None
    )
    measured_at = latest_sensor.measured_at if latest_sensor is not None else None

    history = await _latest_history(db, factory_id)
    factory_status = factory.status.upper() if factory and factory.status else None
    if factory_status not in {"NORMAL", "WARNING", "ERROR"}:
        factory_status = _status_from_temp(temperature, measured_at)
    node_id = os.getenv("NODE_ID", "node_A")
    peltier_status = (
        status_store.get_peltier_status(node_id, factory_id)
        or status_store.get_peltier_status_by_factory(factory_id)
    )
    if peltier_status and peltier_status.get("node_id"):
        node_id = peltier_status["node_id"]

    return {
        "success": True,
        "message": "ok",
        "data": {
            "factory_id": factory_id,
            "node_id": node_id,
            "factory_name": factory.name if factory and factory.name else f"Factory {factory_id}",
            "status": factory_status,
            "temperature_c": temperature,
            "humidity_pct": humidity,
            "peltier": peltier_status if peltier_status and peltier_status.get("available", False) else None,
            "current_schedule_mode": current_schedule.mode if current_schedule else "OFF",
            "next_schedule": {
                "start_at": _iso(next_schedule.start_at) if next_schedule else None,
                "end_at": _iso(next_schedule.end_at) if next_schedule else None,
                "mode": next_schedule.mode if next_schedule else "OFF",
            },
            "last_updated_at": _iso(measured_at),
            "history": history,
        },
    }
