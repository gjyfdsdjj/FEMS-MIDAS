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
