from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import ReadonlyToken

# QR 읽기 전용 토큰 발급
# POST /api/v1/readonly/tokens 요청 시 새로운 토큰 생성에 사용
# 특정 factory_id와 연결된 토큰을 생성하고, 만료 시간과 활성화 여부를 readonly_tokens 테이블에 저장
async def create_readonly_token(
    db: AsyncSession,
    factory_id: int,
    token: str,
    expires_at: datetime | None,
):
    readonly_token = ReadonlyToken(
        factory_id=factory_id,
        token=token,
        is_active=True,
        expires_at=expires_at,
    )

    db.add(readonly_token)
    await db.commit()
    await db.refresh(readonly_token)

    return {
        "id": readonly_token.id,
        "factory_id": readonly_token.factory_id,
        "token": readonly_token.token,
        "is_active": readonly_token.is_active,
        "expires_at": readonly_token.expires_at,
        "created_at": readonly_token.created_at,
    }

# QR 읽기 전용 토큰 조회 
# GET /api/v1/readonly/{token} 요청 시 토큰 유효성 검증에 사용 
# 토큰과 연결된 factory_id, 만료 시간, 활성화 여부를 조회
async def get_readonly_token(db: AsyncSession, token: str):
    result = await db.execute(
        select(ReadonlyToken)
        .where(ReadonlyToken.token == token)
    )

    readonly_token = result.scalar_one_or_none()

    if readonly_token is None:
        return None

    return {
        "id": readonly_token.id,
        "factory_id": readonly_token.factory_id,
        "token": readonly_token.token,
        "is_active": readonly_token.is_active,
        "expires_at": readonly_token.expires_at,
        "created_at": readonly_token.created_at,
    }
    
