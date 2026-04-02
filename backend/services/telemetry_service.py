# backend/services/telemetry_service.py
# 센서 데이터 저장 및 조회 로직
#
# - save_telemetry(payload) : sensor_logs INSERT, factories 최신 상태 UPDATE
#
# - get_live(factory_id?) : 공장별 최신 telemetry 1건 조회
#
# - get_history(factory_id, metric, from_dt, to_dt, interval)
#     sensor_logs 시계열 조회 후 interval 단위 평균 집계
#     반환: List[{timestamp, value}]
#
# - check_communication_status(factory_id)
#     last_seen_at 기준 경과 시간 계산
#     < 10초: OK / 10~30초: DELAYED / > 30초: DISCONNECTED
#
# - get_chart_hourly(date, chart_type)
#     시간대별 before/after 최적화 비용 or 전력량 계산
