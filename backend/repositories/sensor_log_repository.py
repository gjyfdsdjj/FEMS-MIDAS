from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# 공장별 최신 센서 로그 조회
# 온도 이탈 감지(TEMP_RANGE_OUT) 검사용
# - 각 factory_id별 가장 최근 measured_at 기준 로그 1건씩 조회
async def get_latest_sensor_logs(db: AsyncSession):
    result = await db.execute(text("""
        SELECT DISTINCT ON (factory_id)
            factory_id,
            temperature_c,
            measured_at
        FROM sensor_logs
        ORDER BY factory_id, measured_at DESC
    """))
    return [dict(row) for row in result.mappings().all()]

# 공장별 5분 이전 센서 로그 중 가장 최근 로그 1개 조회
# 온도 급변 감지(TEMP_SPIKE) 검사용 
# 
async def get_sensor_logs_before_5_minutes(db: AsyncSession):
    result = await db.execute(text("""
        SELECT DISTINCT ON (factory_id)
            factory_id,
            temperature_c,
            measured_at
        FROM sensor_logs
        WHERE measured_at <= NOW() - INTERVAL '5 minutes'
        ORDER BY factory_id, measured_at DESC
    """))
    return [dict(row) for row in result.mappings().all()]