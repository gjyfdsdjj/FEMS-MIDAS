# backend/mqtt/subscriber.py
# MQTT 수신 처리 (Edge → Backend)
#
# - MQTTSubscriber 클래스
#     start() : 브로커 연결 후 토픽 구독 시작 (백그라운드 루프)
#     stop()  : 연결 종료
#
# - 구독 토픽
#     factory/+/+/telemetry → on_telemetry()
#     factory/+/+/ack       → on_ack()
#     factory/+/+/alert     → on_alert()
#     factory/+/+/buffered  → on_buffered() (통신 복구 후 재전송 배치)
#
# - on_telemetry(payload)
#     sensor_logs 저장, factories 최신 상태 업데이트, 통신 타이머 리셋
#
# - on_ack(payload)
#     control_logs에 APPLIED / FAILED 결과 업데이트
#
# - on_alert(payload)
#     alerts 저장 후 alert_service.send_telegram() 호출
#
# - on_buffered(payload)
#     오프라인 중 적재된 telemetry 리스트 일괄 저장
