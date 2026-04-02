# backend/services/alert_service.py
# 알림 생성, 저장, Telegram 발송 로직
#
# - create_alert(factory_id, level, alert_type, message)
#     중복 window 확인 (300초 내 동일 factory_id + type 존재 시 skip)
#     alerts 테이블 INSERT
#     CRITICAL / WARNING 이면 send_telegram 호출
#
# - send_telegram(message)
#     환경변수 TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID 사용
#     httpx.AsyncClient로 발송
#     실패 시 system_events에 에러 기록 (알림 실패가 서비스 중단으로 이어지지 않도록)
#
# - acknowledge_alert(alert_id, acknowledged_by)
#     is_acknowledged=True, acknowledged_at, acknowledged_by 업데이트
#
# - get_alerts(factory_id?, level?, is_acknowledged?, limit, cursor)
#     alerts 커서 페이지네이션
#
# - get_alert_rules()
#     현재 임계값 반환 (temp_deviation_threshold_c / communication_timeout_sec / dedup_window_sec)
