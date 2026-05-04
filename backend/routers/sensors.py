from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db
from database.models import SensorLog


router = APIRouter(prefix="/api/v1/sensors", tags=["sensors"])

METRIC_COLUMNS = {
    "temperature": SensorLog.temperature_c,
    "humidity": SensorLog.humidity_pct,
}
INTERVAL_SECONDS = {
    "1m": 60,
    "5m": 300,
    "30m": 1800,
    "1h": 3600,
}


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return _as_utc(dt).isoformat()


def _row_to_payload(row: SensorLog) -> dict:
    measured_at = _as_utc(row.measured_at) if row.measured_at else None
    age_seconds = None
    communication = "UNKNOWN"
    if measured_at is not None:
        age_seconds = max(0, int((datetime.now(timezone.utc) - measured_at).total_seconds()))
        communication = "OK" if age_seconds < 10 else "DELAYED" if age_seconds < 30 else "DISCONNECTED"

    return {
        "factory_id": row.factory_id,
        "node_id": row.node_id,
        "temperature_c": float(row.temperature_c) if row.temperature_c is not None else None,
        "humidity_pct": float(row.humidity_pct) if row.humidity_pct is not None else None,
        "measured_at": _iso(row.measured_at),
        "logged_at": _iso(row.logged_at),
        "age_seconds": age_seconds,
        "communication": communication,
    }


@router.get("/live")
async def get_live_sensors(
    factory_id: Optional[int] = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
):
    query = select(SensorLog).order_by(SensorLog.measured_at.desc(), SensorLog.id.desc())
    if factory_id is not None:
        query = query.where(SensorLog.factory_id == factory_id).limit(1)

    result = await db.execute(query)
    rows = result.scalars().all()

    latest_by_factory: dict[int, SensorLog] = {}
    for row in rows:
        if row.factory_id not in latest_by_factory:
            latest_by_factory[row.factory_id] = row

    data = [_row_to_payload(row) for row in latest_by_factory.values()]
    data.sort(key=lambda item: item["factory_id"])
    return {"success": True, "count": len(data), "data": data}


@router.get("/history")
async def get_sensor_history(
    factory_id: int = Query(..., ge=1),
    metric: str = Query("temperature"),
    from_dt: Optional[datetime] = Query(default=None, alias="from"),
    to_dt: Optional[datetime] = Query(default=None, alias="to"),
    interval: str = Query("5m"),
    db: AsyncSession = Depends(get_db),
):
    metric_column = METRIC_COLUMNS.get(metric)
    if metric_column is None:
        raise HTTPException(status_code=400, detail="metric must be temperature or humidity")

    interval_seconds = INTERVAL_SECONDS.get(interval)
    if interval_seconds is None:
        raise HTTPException(status_code=400, detail="interval must be 1m, 5m, 30m, or 1h")
    to_dt = _as_utc(to_dt or datetime.now(timezone.utc))
    from_dt = _as_utc(from_dt or (to_dt - timedelta(hours=24)))
    if from_dt >= to_dt:
        raise HTTPException(status_code=400, detail="from must be before to")

    result = await db.execute(
        select(SensorLog.measured_at, metric_column)
        .where(SensorLog.factory_id == factory_id)
        .where(SensorLog.measured_at >= from_dt)
        .where(SensorLog.measured_at <= to_dt)
        .order_by(SensorLog.measured_at)
    )
    rows = result.all()

    buckets: dict[int, list[float]] = {}
    for measured_at, value in rows:
        if measured_at is None or value is None:
            continue
        ts = int(_as_utc(measured_at).timestamp())
        bucket_start = ts - (ts % interval_seconds)
        buckets.setdefault(bucket_start, []).append(float(value))

    points = []
    for bucket_start, values in sorted(buckets.items()):
        points.append(
            {
                "timestamp": datetime.fromtimestamp(bucket_start, tz=timezone.utc).isoformat(),
                "value": round(sum(values) / len(values), 3),
                "sample_count": len(values),
            }
        )

    return {
        "success": True,
        "factory_id": factory_id,
        "metric": metric,
        "interval": interval,
        "count": len(points),
        "data": points,
    }
