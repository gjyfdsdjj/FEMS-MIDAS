from datetime import datetime, timezone
from sqlalchemy import select, cast
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Alert

# 300초 내 동일한 알림이 있는지 확인
async def check_duplicate_alert(db: AsyncSession, factory_id: int, alert_type: str, time_limit: datetime) -> bool:
    result = await db.execute(
        select(Alert)
        .where(Alert.factory_id == factory_id) # 조건 1: 같은 공장
        .where(Alert.alert_type == alert_type) # 조건 2: 같은 알림 종류
        .where(Alert.created_at >= time_limit) # 조건 3: 300초 이내 
        .limit(1)
    )
    
    alert = result.scalar_one_or_none()
    return alert is not None

# 새로운 알림을 DB에 인서트하고 결과를 딕셔너리로 반환
async def insert_alert(db: AsyncSession, factory_id: int, priority: str, severity: str, alert_type: str, message: str):
    new_alert = Alert(
        factory_id=factory_id,
        priority=cast(priority, ENUM(name="alerts_priority", create_type=False)),
        severity=cast(severity, ENUM(name="alerts_severity", create_type=False)),
        alert_type=alert_type,
        message=message
    )
    
    db.add(new_alert)
    await db.commit()
    await db.refresh(new_alert)
    
    return {
        "id": new_alert.id,
        "factory_id": new_alert.factory_id,
        "priority": new_alert.priority,
        "severity": new_alert.severity,
        "alert_type": new_alert.alert_type,
        "message": new_alert.message,
        "created_at": new_alert.created_at,
    }

# DB에서 alert_id에 해당하는 알림을 찾아 ack_at 컬럼을 현재 시간으로 업데이트
async def update_alert_acknowledge(db: AsyncSession, alert_id: int):
   
    # 수정할 알림 데이터 하나 가져오기 
    alert = await db.get(Alert, alert_id)

    if alert is None:
        return None
    
    # 값 변경 
    alert.ack_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(alert)

    return alert
