from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import SensorLogArchive


async def get_recent_archive_sensor_logs(
    db: AsyncSession,
    factory_id: int,
    limit: int = 100,
) -> list[dict]:

    subquery = (
        select(SensorLogArchive.id)
        .where(SensorLogArchive.factory_id == factory_id)
        .order_by(SensorLogArchive.measured_at.desc())
        .limit(limit)
        .subquery()
    )

    result = await db.execute(
        select(SensorLogArchive)
        .where(SensorLogArchive.id.in_(select(subquery.c.id)))
        .order_by(SensorLogArchive.measured_at.asc())
    )

    rows = result.scalars().all()

    return [
        {
            "id": row.id,
            "factory_id": row.factory_id,
            "node_id": row.node_id,
            "temperature_c": float(row.temperature_c) if row.temperature_c is not None else None,
            "humidity_pct": float(row.humidity_pct) if row.humidity_pct is not None else None,
            "measured_at": row.measured_at,
            "logged_at": row.logged_at,
        }
        for row in rows
    ]