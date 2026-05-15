from datetime import datetime, timedelta, timezone

from sqlalchemy import select 
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Factory, Schedule, SensorLog

# factory_id에 해당하는 공장 정보를 조회
# QR 조회 화면에 표시할 공장명, 공장 상태 등을 가져올 때 사용
async def get_factory_by_id(db: AsyncSession, factory_id: int):
    return await db.get(Factory, factory_id)

# 특정 공장의 가장 최근 센서 로그 1건 조회
# 현재 온도, 습도, 마지막 측정 시간을 화면에 표시할 때 사용 
async def get_latest_sensor_log(db: AsyncSession, factory_id: int):
    result = await db.execute(
        select(SensorLog)
        .where(SensorLog.factory_id == factory_id)
        .order_by(SensorLog.measured_at.desc(), SensorLog.id.desc())
        .limit(1)
    )

    return result.scalar_one_or_none()

# 현재 시간 기준으로 실행 중인 스케줄 조회  
async def get_current_schedule(db: AsyncSession, factory_id: int):
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(Schedule)
        .where(Schedule.factory_id == factory_id)
        .where(Schedule.start_at <= now)
        .where(Schedule.end_at >= now)
        .order_by(Schedule.start_at.desc())
        .limit(1)
    )

    return result.scalar_one_or_none()

# 현재 시간 이후에 예정된 가장 가까운 스케줄 1건 조회
async def get_next_schedule(db: AsyncSession, factory_id: int):
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(Schedule)
        .where(Schedule.factory_id == factory_id)
        .where(Schedule.start_at > now)
        .order_by(Schedule.start_at)
        .limit(1)
    )

    return result.scalar_one_or_none()

# 최근 N시간 동안의 온도 이력 조회
# 기본값은 최근 24시간이며, QR 화면의 온도 그래프 데이터로 사용 
async def get_temperature_history(
        db: AsyncSession,
        factory_id: int,
        hours: int = 24,
) -> list[dict]:
    
    since = datetime.now(timezone.utc)-timedelta(hours=hours) # 24시간 전 시각

    result = await db.execute(
        select(SensorLog.temperature_c, SensorLog.measured_at)
        .where(SensorLog.factory_id == factory_id)
        .where(SensorLog.measured_at >= since)
        .order_by(SensorLog.measured_at)
    )

    return [
        { 
            "timestamp": row.measured_at, 
             "temperature_c": float(row.temperature_c) 
            if row.temperature_c is not None 
            else None, 
        }
        for row in result.all()
        if row.measured_at is not None
    ]