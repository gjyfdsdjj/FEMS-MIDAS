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

from datetime import datetime, timezone

from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.repositories.readonly_token_repository import get_readonly_token
from backend.repositories.readonly_repository import (
    get_factory_by_id,
    get_latest_sensor_log,
    get_current_schedule,
    get_next_schedule,
    get_temperature_history,
)

async def get_readonly_data(db: AsyncSession, token: str):
    readonly_token = await get_readonly_token(db, token)

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
    
    expires_at = readonly_token["expires_at"]

    if expires_at is not None:
        now = datetime.now(timezone.utc)

        if expires_at.tzinfo is None:
           expires_at = expires_at.replace(tzinfo=timezone.utc)

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

    factory_id = readonly_token["factory_id"]

    factory = await get_factory_by_id(db, factory_id)
    latest_sensor_log = await get_latest_sensor_log(db, factory_id)
    current_schedule = await get_current_schedule(db, factory_id)
    next_schedule = await get_next_schedule(db, factory_id)
    temperature_history = await get_temperature_history(db, factory_id)

    return {
        "factory": factory,
        "latest_sensor_log" : latest_sensor_log,
        "current_schedule": current_schedule,
        "next_schedule": next_schedule,
        "temperature_history": temperature_history,
    }