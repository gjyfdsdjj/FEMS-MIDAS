# backend/routers/readonly.py
# QR 모바일 읽기 전용 엔드포인트
#
# POST /api/v1/readonly/tokens
#   - 권한: admin
#   - factory_id, expires_in_minutes 받아 readonly_token 발급
#   - readonly_tokens 테이블 저장
#   - 응답: token, readonly_url, expires_at
#
# GET /api/v1/readonly/{token}
#   - 권한: readonly_token (Bearer 불필요, 토큰 자체가 URL에 포함)
#   - 토큰 유효성(만료, 공장 매핑) 확인
#   - 해당 공장의 최신 온습도, 현재 스케줄 모드, 다음 스케줄 블록만 반환
#   - 제어 관련 필드 일절 포함하지 않음

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1/readonly", tags=["readonly"])

# 테스트용 더미 데이터 
readonly_dummy_data = {
    "rdonly_test_1": {
        "factory_id": 1,
        "factory_name": "공장 1",
        "status": "NORMAL",
        "temperature_c": -21.4,
        "humidity_pct": 41.2,
        "current_schedule_mode": "ON",
        "next_schedule": {
            "start_at": "2026-03-12T21:00:00+09:00",
            "end_at": "2026-03-12T23:00:00+09:00",
            "mode": "ON"
        },
        "last_updated_at": "2026-03-12T19:29:58+09:00"
    }
}

@router.get("/{token}")
def get_readonly_factory_info(token: str):
    factory_info = readonly_dummy_data.get(token)

    if not factory_info:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": {
                    "code": "NOT_FOUND",
                    "message": "readonly token not found",
                    "details": {}
                }
            }
        )
    
    return {
        "success": True,
        "message": "ok",
        "data": factory_info
    }
