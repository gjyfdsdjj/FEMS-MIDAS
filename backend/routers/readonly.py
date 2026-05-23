from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db
from services.readonly_service import (
    get_readonly_data,
    issue_readonly_token,
)


router = APIRouter(prefix="/api/v1/readonly", tags=["readonly"])

# QR 읽기 전용 토큰 발급 요청 DTO
class ReadonlyTokenCreateRequest(BaseModel):
    factory_id: int
    expires_in_minutes: int = 60

# QR 읽기 전용 토큰 발급 API
# 특정 factory_id에 연결된 readonly token을 생성하고 DB에 저장한 뒤,
# 프론트에서 사용할 readonly_url과 만료 시간을 반환
@router.post("/tokens")
async def create_readonly_token(
    request: ReadonlyTokenCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await issue_readonly_token(
        db=db,
        factory_id=request.factory_id,
        expires_in_minutes=request.expires_in_minutes,
    )

    return {
        "success": True,
        "message": "readonly token created",
        "data": result,
    }

# QR 읽기 전용 공장 조회 API
# QR URL에 포함된 token을 기준으로 토큰 유효성을 검증하고,
# 유효한 경우 해당 공장의 최신 센서 데이터, 스케줄 정보, 온도 이력을 반환
@router.get("/{token}")
async def get_readonly_factory_info(token: str, db: AsyncSession = Depends(get_db)):
    result = await get_readonly_data(db, token)

    if isinstance(result, JSONResponse):
        return result

    return {
        "success": True,
        "message": "ok",
        "data": result,
    }
