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
