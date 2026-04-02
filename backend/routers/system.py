# backend/routers/system.py
# 시스템 상태 엔드포인트
#
# GET /api/v1/system/status
#   - 권한: viewer
#   - 상단 상태바용: 전체 제어 모드, 통신 상태, 위험도 지수
#     가동 공장 수, 스케줄러 마지막 실행 시각, 환경 가중치 갱신 시각
#
# GET /api/v1/system/events
#   - 권한: admin
#   - Query: level?, factory_id?, limit?, cursor?
#   - system_events 테이블 커서 페이지네이션
