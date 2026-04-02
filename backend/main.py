# backend/main.py
# FastAPI 앱 진입점
#
# - FastAPI 앱 인스턴스 생성
# - CORS 미들웨어 설정 (Streamlit 프론트 허용)
# - 모든 라우터 include_router로 등록 (/api/v1 prefix)
# - lifespan 이벤트:
#     startup : DB 연결 확인, MQTT subscriber 시작, APScheduler 시작
#     shutdown: MQTT 연결 종료, APScheduler 종료
# - WebSocket 엔드포인트 등록 (/ws/live-data)
#     채널: dashboard.summary / factory.{id}.live / alerts.live / schedule.live / system.events
# - 전역 예외 핸들러 (공통 에러 응답 envelope 적용)
