from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# 공장별 마지막 센서 수신 시간 조회
# - 통신 타임아웃 감지(COMMUNICATION_TIMEOUT)에 사용
async def get_factory_last_seen_times(db: AsyncSession):
    result = await db.execute(text("""
        SELECT 
            factory_id,
            last_seen_at
        FROM factories
    """))

    return [dict(row) for row in result.mappings().all()]