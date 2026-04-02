# backend/routers/alerts.py
# 알림 엔드포인트
#
# GET /api/v1/alerts
#   - 권한: viewer
#   - Query: factory_id?, level?, is_acknowledged?, limit?, cursor?
#   - 최근 알림 목록 커서 페이지네이션
#
# PATCH /api/v1/alerts/{alert_id}/ack
#   - 권한: admin
#   - is_acknowledged=True, acknowledged_by, acknowledged_at 저장
#
# POST /api/v1/alerts/test
#   - 권한: admin
#   - 지정 공장으로 Telegram 테스트 메시지 발송
#
# GET /api/v1/alerts/rules
#   - 권한: admin
#   - 현재 알림 임계값 조회
#     temp_deviation_threshold_c / communication_timeout_sec / dedup_window_sec
