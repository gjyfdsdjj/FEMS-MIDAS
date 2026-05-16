# backend/services/readonly_service.py
# QR 읽기 전용 토큰 발급 및 조회 로직
#
# - issue_token(factory_id, expires_in_minutes)
#     secrets.token_urlsafe로 토큰 생성
#     readonly_tokens 테이블 INSERT (factory_id, token, expires_at)
#     반환: token, readonly_url, expires_at
#
# - get_readonly_data(token)
#     토큰 유효성 확인 (존재 여부, 만료 여부)
#     해당 공장 최신 센서 데이터 조회
#     현재 스케줄 모드, 다음 스케줄 블록 조회
#     제어 관련 필드(manual_stop, pwm_pct 등) 제외하고 반환

import os
import secrets

from mqtt.status_store import status_store

from datetime import datetime, timezone, timedelta

from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from repositories.readonly_token_repository import (
    get_readonly_token,
    create_readonly_token,
)

from repositories.readonly_repository import (
    get_factory_by_id,
    get_latest_sensor_log,
    get_current_schedule,
    get_next_schedule,
    get_temperature_history,
)

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

# 공장 QR 조회용 읽기 전용 토큰 생성 후, DB에 저장한 뒤, 
# 프론트에서 사용할 URL까지 만들어 반환 
async def issue_readonly_token(
        db: AsyncSession,
        factory_id: int,
        expires_in_minutes: int = 60,
):
    token = secrets.token_urlsafe(32)

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)

    await create_readonly_token(
        db=db,
        factory_id=factory_id,
        token=token,
        expires_at=expires_at
    )

    return {
        "factory_id": factory_id,
        "token": token,
        "readonly_url": f"/readonly/{token}",
        "expires_at": _iso(expires_at),
    }


async def get_readonly_data(db: AsyncSession, token: str):
    # 1.  전달받은 QR 토큰이 DB에 존재하는지 조회
    readonly_token = await get_readonly_token(db, token)

    # 2. 토큰이 존재하지 않으면 404 에러 
    if readonly_token is None:
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
    
    # 3. 토큰은 존재하지만 비활성화된 토큰이면 접근 차단 
    if not readonly_token["is_active"]:
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "error": {
                    "code": "FORBIDDEN",
                    "message": "readonly token is inactive",
                    "details": {},
                },
            },
        ) 
    
    # 4. 토큰 만료 시간 가져옴
    expires_at = readonly_token["expires_at"]

    # 5. 만료 시간이 있다면 현재 시간과 비교 
    if expires_at is not None:
        now = datetime.now(timezone.utc)

        if expires_at.tzinfo is None:
           expires_at = expires_at.replace(tzinfo=timezone.utc)

        # 6. 이미 만료된 토큰이면 접근 차단 
        if expires_at < now:
            return JSONResponse(
                status_code=403,
                content={
                    "success": False,
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "readonly token is expired",
                        "details": {},
                    },
                },
            )
    # 7. 유효한 토큰이면 토큰에 연결된 공장 ID 가져옴 
    factory_id = readonly_token["factory_id"]

    factory = await get_factory_by_id(db, factory_id)
    latest_sensor_log = await get_latest_sensor_log(db, factory_id)
    current_schedule = await get_current_schedule(db, factory_id)
    next_schedule = await get_next_schedule(db, factory_id)
    temperature_history = await get_temperature_history(db, factory_id)

    node_id = ( 
        latest_sensor_log.get("node_id") 
        if latest_sensor_log and latest_sensor_log.get("node_id")
        else os.getenv("NODE_ID", "node_A")
    )
    
    peltier_status = (
        status_store.get_peltier_status(node_id, factory_id)
        or status_store.get_peltier_status_by_factory(factory_id)
    )

    if peltier_status and peltier_status.get("node_id"):
        node_id = peltier_status["node_id"]

    temperature = latest_sensor_log.get("temperature_c") if latest_sensor_log else None
    humidity = latest_sensor_log.get("humidity_pct") if latest_sensor_log else None
    measured_at = latest_sensor_log.get("measured_at") if latest_sensor_log else None

    factory_name = factory.get("name") if factory and factory.get("name") else f"Factory {factory_id}"

    factory_status = factory.get("status") if factory else None
    factory_status = factory_status.upper() if factory_status else None

    if factory_status not in {"NORMAL", "WARNING", "ERROR"}:
        factory_status = _status_from_temp(temperature, measured_at)

    current_schedule_mode = current_schedule.get("mode") if current_schedule else "OFF"

    next_schedule_start_at = next_schedule.get("start_at") if next_schedule else None
    next_schedule_end_at = next_schedule.get("end_at") if next_schedule else None
    next_schedule_mode = next_schedule.get("mode") if next_schedule else "OFF"

    return {
        "factory_id": factory_id,
        "node_id": node_id,
        "factory_name": factory_name,
        "status": factory_status,
        "temperature_c": temperature,
        "humidity_pct": humidity,
        "peltier": peltier_status if peltier_status and peltier_status.get("available", False) else None,
        "current_schedule_mode": current_schedule_mode,
        "next_schedule": {
            "start_at": _iso(next_schedule_start_at),
            "end_at": _iso(next_schedule_end_at),
            "mode": next_schedule_mode,
        },
        "last_updated_at": _iso(measured_at),
        "history": temperature_history,
}